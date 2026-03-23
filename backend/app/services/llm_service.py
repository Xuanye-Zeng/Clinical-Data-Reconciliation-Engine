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
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return bool(settings.ollama_base_url) and bool(settings.ollama_model)


def _strip_code_fences(text: str) -> str:
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
    cleaned = _strip_code_fences(text)
    candidates = [cleaned]

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
        preferred_keys = ("reasoning", "explanation", "summary", "message", "text")
        for key in preferred_keys:
            nested = _extract_reasoning_value(value.get(key))
            if nested:
                return nested
        for nested_value in value.values():
            nested = _extract_reasoning_value(nested_value)
            if nested:
                return nested

    return None


def _get_cached_response(cache_scope: str, payload: dict[str, Any]) -> Any | None:
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


def _request_json_response(prompt_payload: dict[str, Any]) -> Any | None:
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

    parsed = _parse_json_payload(str(response_payload.get("response", "")))
    if parsed is None:
        logger.warning("Ollama response could not be parsed as JSON")
    else:
        logger.info("Ollama response parsed successfully")
    return parsed


def generate_reconciliation_enrichment(
    payload: ReconcileMedicationRequest,
    winning_source: MedicationSource,
    alternatives: list[str],
    fallback_reasoning: str,
) -> dict[str, Any] | None:
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

    if not isinstance(parsed, dict):
        logger.info("Reconciliation enrichment fallback used")
        return None

    reasoning = _extract_reasoning_value(parsed)

    if not isinstance(reasoning, str) or not reasoning.strip():
        logger.info("Reconciliation enrichment fallback used due to invalid reasoning payload: %s", parsed)
        return None

    cleaned_reasoning = " ".join(reasoning.strip().split())
    if len(cleaned_reasoning) < 30:
        logger.info("Reconciliation enrichment fallback used because explanation was too short")
        return None

    if len(cleaned_reasoning) > 320:
        cleaned_reasoning = cleaned_reasoning[:317].rstrip() + "..."

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

    existing_pairs = {(issue.field, issue.issue) for issue in current_issues}
    generated_issues: list[QualityIssue] = []

    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            continue

        field = raw_issue.get("field")
        issue_text = raw_issue.get("issue")
        severity = raw_issue.get("severity")
        if not isinstance(field, str) or not isinstance(issue_text, str) or severity not in {"low", "medium", "high"}:
            continue
        if (field, issue_text) in existing_pairs:
            continue

        generated_issues.append(QualityIssue(field=field, issue=issue_text, severity=severity))

    logger.info("Data quality issue generation applied from Ollama with %s issues", len(generated_issues[:2]))
    return generated_issues[:2]
