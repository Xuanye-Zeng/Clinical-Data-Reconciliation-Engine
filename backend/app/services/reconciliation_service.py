"""
Medication reconciliation service.

This is the core decision engine. It scores competing medication sources
using reliability, recency, and clinical context, then selects the most
likely truth. The LLM is only called afterward to optionally polish the
explanation text -- it never influences the selected medication, confidence
score, or safety check.
"""

from datetime import date

from app.models.reconcile import (
    MedicationSource,
    ReconcileMedicationRequest,
    ReconcileMedicationResponse,
)
from app.services.llm_service import generate_reconciliation_enrichment


# Weights that map source_reliability strings to numeric values.
# "high" sources (e.g. hospital EHR, primary care) are trusted more.
# Unknown values fall back to 0.65 so the system doesn't crash on unexpected input.
RELIABILITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.5,
}


def _safe_egfr(payload: ReconcileMedicationRequest) -> float | None:
    """Safely extract eGFR as a number. Returns None if missing or non-numeric.

    recent_labs is dict[str, Any], so the client could send a string like "45"
    instead of the number 45. This prevents a TypeError when comparing.
    """
    raw = payload.patient_context.recent_labs.get("eGFR")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _days_since(source: MedicationSource) -> int:
    """Days since the source was last updated or filled.
    Missing dates are treated as 365 days old (worst case).
    """
    candidate_date = source.last_updated or source.last_filled
    if candidate_date is None:
        return 365
    return max((date.today() - candidate_date).days, 0)


def _recency_score(source: MedicationSource) -> float:
    """Map days-since-update to a 0-1 score.
    More recent sources get higher scores:
      <= 7 days  -> 1.0
      <= 30 days -> 0.85
      <= 90 days -> 0.7
      > 90 days  -> 0.5
    """
    days = _days_since(source)
    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.85
    if days <= 90:
        return 0.7
    return 0.5


def _clinical_context_adjustment(source: MedicationSource, payload: ReconcileMedicationRequest) -> float:
    """Small score bump or penalty based on clinical context.

    When kidney function is reduced (eGFR <= 45), a lower metformin dose
    is clinically more appropriate. So we boost 500mg (+0.12) and penalize
    1000mg (-0.1) to nudge the scoring toward the safer dose.
    """
    egfr = _safe_egfr(payload)
    medication = source.medication.lower()

    if egfr is not None and egfr <= 45 and "metformin 500mg" in medication:
        return 0.12
    if egfr is not None and egfr <= 45 and "metformin 1000mg" in medication:
        return -0.1
    return 0.0


def _score_source(source: MedicationSource, payload: ReconcileMedicationRequest) -> float:
    """Composite score = reliability + recency + clinical adjustment.

    The highest-scoring source becomes the selected medication.
    Typical range is roughly 1.15 to 2.12 for realistic inputs.
    """
    reliability = RELIABILITY_WEIGHTS.get(source.source_reliability.lower(), 0.65)
    return reliability + _recency_score(source) + _clinical_context_adjustment(source, payload)


def _build_rule_reasoning(
    payload: ReconcileMedicationRequest,
    winning_source: MedicationSource,
    alternatives: list[str],
) -> str:
    """Generate a deterministic explanation for the reconciliation decision.
    This is the fallback if the LLM enhancement fails or is unavailable.
    """
    reasoning_parts = [
        f"{winning_source.system} was selected because it combines {winning_source.source_reliability} source reliability",
        "and the strongest recency signal.",
    ]

    egfr = _safe_egfr(payload)
    if egfr is not None and egfr <= 45 and "500mg" in winning_source.medication.lower():
        reasoning_parts.append("The lower dose also aligns with reduced kidney function (eGFR 45 or below).")

    if alternatives:
        reasoning_parts.append(f"Conflicting alternatives were reviewed: {', '.join(alternatives)}.")

    return " ".join(reasoning_parts)


def _build_recommended_actions(winning_source: MedicationSource) -> list[str]:
    return [
        f"Update downstream systems to reflect {winning_source.medication}.",
        "Confirm the active dose with the patient or dispensing pharmacy.",
    ]


def _build_safety_check(payload: ReconcileMedicationRequest, winning_source: MedicationSource) -> str:
    """Flag REVIEW when high-dose metformin is selected for a patient with reduced kidney function."""
    egfr = _safe_egfr(payload)
    safety_check = "PASSED"
    if egfr is not None and egfr <= 45 and "1000mg" in winning_source.medication.lower():
        safety_check = "REVIEW"
    return safety_check


def reconcile_medication(payload: ReconcileMedicationRequest) -> ReconcileMedicationResponse:
    """Main entry point for the reconciliation flow.

    Steps:
    1. Score and rank all sources
    2. Select the highest-scoring source as the reconciled medication
    3. Compute confidence by mapping the composite score to a 0-1 range
    4. Generate rule-based reasoning, actions, and safety check
    5. Optionally call the LLM to rewrite reasoning in clinician-friendly language
    6. If LLM fails or is unavailable, keep the rule-based reasoning
    """
    # Step 1-2: rank sources and pick the winner
    ranked_sources = sorted(
        payload.sources,
        key=lambda source: _score_source(source, payload),
        reverse=True,
    )
    winning_source = ranked_sources[0]
    alternatives = [source.medication for source in ranked_sources[1:]]

    # Step 3: map composite score to 0-1 confidence.
    # Divide by 2.2 (just above the practical max score) and clamp to [0.35, 0.96].
    # Floor of 0.35 avoids misleadingly low confidence for reasonable inputs.
    # Ceiling of 0.96 avoids implying certainty a heuristic system can't guarantee.
    confidence = min(max(_score_source(winning_source, payload) / 2.2, 0.35), 0.96)

    # Step 4: build rule-based outputs
    reasoning = _build_rule_reasoning(payload, winning_source, alternatives)
    recommended_actions = _build_recommended_actions(winning_source)
    safety_check = _build_safety_check(payload, winning_source)

    if safety_check == "REVIEW":
        recommended_actions.append("Review whether the current dose is appropriate for the patient's renal function.")

    # Step 5-6: optional LLM enhancement with automatic fallback
    llm_enrichment = generate_reconciliation_enrichment(
        payload=payload,
        winning_source=winning_source,
        alternatives=alternatives,
        fallback_reasoning=reasoning,
    )
    if llm_enrichment:
        reasoning = llm_enrichment["reasoning"]

    return ReconcileMedicationResponse(
        reconciled_medication=winning_source.medication,
        confidence_score=round(confidence, 2),
        reasoning=reasoning,
        recommended_actions=recommended_actions,
        clinical_safety_check=safety_check,
    )
