from datetime import date

from app.models.reconcile import (
    MedicationSource,
    ReconcileMedicationRequest,
    ReconcileMedicationResponse,
)
from app.services.llm_service import generate_reconciliation_enrichment


RELIABILITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.5,
}


def _safe_egfr(payload: ReconcileMedicationRequest) -> float | None:
    raw = payload.patient_context.recent_labs.get("eGFR")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _days_since(source: MedicationSource) -> int:
    candidate_date = source.last_updated or source.last_filled
    if candidate_date is None:
        return 365
    return max((date.today() - candidate_date).days, 0)


def _recency_score(source: MedicationSource) -> float:
    days = _days_since(source)
    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.85
    if days <= 90:
        return 0.7
    return 0.5


def _clinical_context_adjustment(source: MedicationSource, payload: ReconcileMedicationRequest) -> float:
    egfr = _safe_egfr(payload)
    medication = source.medication.lower()

    if egfr is not None and egfr <= 45 and "metformin 500mg" in medication:
        return 0.12
    if egfr is not None and egfr <= 45 and "metformin 1000mg" in medication:
        return -0.1
    return 0.0


def _score_source(source: MedicationSource, payload: ReconcileMedicationRequest) -> float:
    reliability = RELIABILITY_WEIGHTS.get(source.source_reliability.lower(), 0.65)
    return reliability + _recency_score(source) + _clinical_context_adjustment(source, payload)


def _build_rule_reasoning(
    payload: ReconcileMedicationRequest,
    winning_source: MedicationSource,
    alternatives: list[str],
) -> str:
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
    egfr = _safe_egfr(payload)
    safety_check = "PASSED"
    if egfr is not None and egfr <= 45 and "1000mg" in winning_source.medication.lower():
        safety_check = "REVIEW"
    return safety_check


def reconcile_medication(payload: ReconcileMedicationRequest) -> ReconcileMedicationResponse:
    ranked_sources = sorted(
        payload.sources,
        key=lambda source: _score_source(source, payload),
        reverse=True,
    )
    winning_source = ranked_sources[0]
    alternatives = [source.medication for source in ranked_sources[1:]]
    confidence = min(max(_score_source(winning_source, payload) / 2.2, 0.35), 0.96)

    reasoning = _build_rule_reasoning(payload, winning_source, alternatives)
    recommended_actions = _build_recommended_actions(winning_source)
    safety_check = _build_safety_check(payload, winning_source)

    if safety_check == "REVIEW":
        recommended_actions.append("Review whether the current dose is appropriate for the patient's renal function.")

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
