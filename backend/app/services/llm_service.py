"""
LLM integration service.

This module wraps the local Ollama model as a constrained enhancement layer.
It is NOT a decision engine -- the rule-based services make all final decisions.

Responsibilities:
  - Call the local Ollama model with structured, constrained prompts
  - Parse messy model output into usable JSON
  - Validate that model output meets business constraints before applying it
  - Cache successful responses to reduce repeated inference latency
  - Fall back cleanly when the model is unavailable, slow, or returns bad output
"""

import hashlib
import json
import logging
import os
from typing import Any

import httpx

from app.core.cache import llm_cache
from app.core.config import settings
from app.models.data_quality import DataQualityRequest, QualityIssue
from app.models.reconcile import MedicationSource, ReconcileMedicationRequest


logger = logging.getLogger(__name__)


def llm_enabled() -> bool:
    """Check whether the LLM should be called.

    Disabled during tests (via PYTEST_CURRENT_TEST env var) so unit tests
    stay fast, deterministic, and don't depend on a running Ollama instance.
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return bool(settings.ollama_base_url) and bool(settings.ollama_model)


# ---------------------------------------------------------------------------
# Output parsing helpers
# ---------------------------------------------------------------------------
# Small models often return output that isn't clean JSON: they may wrap it
# in markdown code fences, prepend explanatory text, or nest it in unexpected
# structures. These helpers try to recover usable JSON from messy output.


def _strip_code_fences(text: str) -> str:
    """Remove markdown ``` fences that models sometimes wrap around JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _parse_json_payload(text: str) -> Any | None:
    """Try to extract a JSON object from potentially messy model output.

    Strategy:
    1. Try parsing the cleaned text directly
    2. If that fails, find the outermost { ... } substring and try that
    3. If both fail, return None (caller will fall back)
    """
    cleaned = _strip_code_fences(text)
    candidates = [cleaned]

    # Try extracting the outermost JSON object as a fallback
    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append(cleaned[object_start : object_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return None


def _extract_reasoning_value(value: Any) -> str | None:
    """Recursively extract a reasoning string from an unpredictable structure.

    Models may return reasoning as:
      - a plain string
      - a list of strings
      - a dict with key "reasoning", "explanation", "summary", etc.
      - nested combinations of the above

    This function walks the structure and returns the first usable text.
    """
    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, list):
        text_parts = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if text_parts:
            return " ".join(text_parts)
        for item in value:
            nested = _extract_reasoning_value(item)
            if nested:
                return nested

    if isinstance(value, dict):
        # Check common key names first for faster extraction
        preferred_keys = ("reasoning", "explanation", "summary", "message", "text")
        for key in preferred_keys:
            nested = _extract_reasoning_value(value.get(key))
            if nested:
                return nested
        # Fall back to scanning all values
        for nested_value in value.values():
            nested = _extract_reasoning_value(nested_value)
            if nested:
                return nested

    return None


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def _get_cached_response(cache_scope: str, payload: dict[str, Any]) -> Any | None:
    """Check cache before calling the model. Cache key is a SHA-256 hash of
    the scope + payload + model name, so different prompts and different
    models never collide.
    """
    cache_key = hashlib.sha256(
        json.dumps({"scope": cache_scope, "payload": payload, "model": settings.ollama_model}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cached = llm_cache.get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for scope=%s", cache_scope)
        return cached

    logger.info("LLM cache miss for scope=%s", cache_scope)
    response_payload = _request_json_response(payload)
    if response_payload is not None:
        llm_cache.set(cache_key, response_payload, settings.llm_cache_ttl_seconds)
        logger.info("LLM response cached for scope=%s", cache_scope)

    return response_payload


# ---------------------------------------------------------------------------
# Ollama HTTP call
# ---------------------------------------------------------------------------


def _request_json_response(prompt_payload: dict[str, Any]) -> Any | None:
    """Send a prompt to the local Ollama model and return parsed JSON, or None.

    This function never raises -- all errors are caught and logged so the
    caller can fall back to rule-based output without crashing the request.
    """
    if not llm_enabled():
        logger.info("LLM disabled: Ollama configuration missing")
        return None

    logger.info("Calling Ollama model=%s", settings.ollama_model)
    full_prompt = (
        f"System instructions:\n{prompt_payload['system_prompt']}\n\n"
        f"User request:\n{prompt_payload['user_prompt']}\n\n"
        "Return JSON only."
    )

    try:
        with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
            response = client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "format": "json",
                    "keep_alive": "10m",
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Ollama request failed: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Unexpected Ollama error: %s", exc)
        return None

    try:
        response_payload = response.json()
    except ValueError:
        logger.warning("Ollama returned a non-JSON HTTP response")
        return None

    # Ollama wraps the model output in {"response": "..."} -- extract and parse it
    parsed = _parse_json_payload(str(response_payload.get("response", "")))
    if parsed is None:
        logger.warning("Ollama response could not be parsed as JSON")
    else:
        logger.info("Ollama response parsed successfully")
    return parsed


# ---------------------------------------------------------------------------
# Business-level enrichment functions
# ---------------------------------------------------------------------------


def generate_reconciliation_enrichment(
    payload: ReconcileMedicationRequest,
    winning_source: MedicationSource,
    alternatives: list[str],
    fallback_reasoning: str,
) -> dict[str, Any] | None:
    """Ask the LLM to rewrite the reconciliation reasoning.

    The prompt is deliberately narrow: the model may ONLY rewrite the explanation
    text. It cannot change the selected medication, safety check, or actions.
    If the model output fails any validation check, we return None and the
    caller keeps the rule-based reasoning.
    """
    prompt_payload = {
        "system_prompt": (
            "You are assisting a clinical data reconciliation engine. "
            "Use only the supplied patient context and medication records. "
            "Do not invent facts, diagnose disease, change the selected medication, or create new treatment plans. "
            "You may only rewrite the explanation in clearer clinician-friendly language. "
            "Return strict JSON with one key named reasoning."
        ),
        "user_prompt": json.dumps(
            {
                "task": "Rewrite the reconciliation explanation in concise clinician-friendly language.",
                "constraints": {
                    "reasoning_style": "brief, clinician-friendly, max 2 sentences",
                    "must_preserve_selected_medication": winning_source.medication,
                    "must_not_change_safety_check": True,
                    "must_not_add_new_actions": True,
                },
                "patient_context": payload.patient_context.model_dump(mode="json"),
                "selected_source": winning_source.model_dump(mode="json"),
                "alternatives": alternatives,
                "fallback_reasoning": fallback_reasoning,
            },
            indent=2,
        ),
    }
    parsed = _get_cached_response("reconciliation_reasoning", prompt_payload)

    # --- Validation gate: every check that fails triggers a fallback ---

    if not isinstance(parsed, dict):
        logger.info("Reconciliation enrichment fallback used")
        return None

    reasoning = _extract_reasoning_value(parsed)

    if not isinstance(reasoning, str) or not reasoning.strip():
        logger.info("Reconciliation enrichment fallback used due to invalid reasoning payload: %s", parsed)
        return None

    cleaned_reasoning = " ".join(reasoning.strip().split())

    # Too short = probably garbage
    if len(cleaned_reasoning) < 30:
        logger.info("Reconciliation enrichment fallback used because explanation was too short")
        return None

    # Too long = truncate to keep UI clean
    if len(cleaned_reasoning) > 320:
        cleaned_reasoning = cleaned_reasoning[:317].rstrip() + "..."

    # If the model didn't mention the winning source, prepend it for clarity
    if winning_source.system.lower() not in cleaned_reasoning.lower():
        cleaned_reasoning = f"{winning_source.system} record selected. {cleaned_reasoning}"

    logger.info("Reconciliation enrichment applied from Ollama")
    return {
        "reasoning": cleaned_reasoning,
    }


def generate_additional_quality_issues(
    payload: DataQualityRequest,
    current_issues: list[QualityIssue],
) -> list[QualityIssue]:
    """Ask the LLM to suggest up to 2 additional data quality issues.

    The prompt constrains the model to only flag issues that are directly
    supported by the payload and not already listed. Each returned issue
    is validated for correct structure and deduped against existing issues.
    """
    prompt_payload = {
        "system_prompt": (
            "You are assisting a clinical data quality review system. "
            "Use only the supplied patient record. "
            "Identify up to 2 additional data quality issues that are directly supported by the payload and not already listed. "
            "Do not infer new diagnoses, medications, or clinical events. "
            "Return strict JSON with one key named issues."
        ),
        "user_prompt": json.dumps(
            {
                "task": "Find additional clinically relevant data quality issues.",
                "constraints": {
                    "issue_limit": 2,
                    "allowed_severity_values": ["low", "medium", "high"],
                },
                "patient_record": payload.model_dump(mode="json"),
                "existing_issues": [issue.model_dump(mode="json") for issue in current_issues],
            },
            indent=2,
        ),
    }
    parsed = _get_cached_response("data_quality_issues", prompt_payload)

    if not isinstance(parsed, dict):
        logger.info("Data quality issue generation fallback used")
        return []

    raw_issues = parsed.get("issues")
    if not isinstance(raw_issues, list):
        logger.info("Data quality issue generation fallback used due to invalid payload")
        return []

    # Filter and validate each issue from the model
    existing_pairs = {(issue.field, issue.issue) for issue in current_issues}
    generated_issues: list[QualityIssue] = []

    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            continue

        field = raw_issue.get("field")
        issue_text = raw_issue.get("issue")
        severity = raw_issue.get("severity")

        # Reject if any field is wrong type or severity is not in the allowed set
        if not isinstance(field, str) or not isinstance(issue_text, str) or severity not in {"low", "medium", "high"}:
            continue

        # Skip duplicates
        if (field, issue_text) in existing_pairs:
            continue

        generated_issues.append(QualityIssue(field=field, issue=issue_text, severity=severity))

    # Hard cap at 2 issues regardless of what the model returned
    logger.info("Data quality issue generation applied from Ollama with %s issues", len(generated_issues[:2]))
    return generated_issues[:2]
