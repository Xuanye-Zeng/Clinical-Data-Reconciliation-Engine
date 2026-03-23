# Architecture Notes

## Overview

This project uses a lightweight layered architecture designed for a take-home setting:

- `api/routes`: thin HTTP layer
- `models`: request and response contracts
- `services`: business logic and orchestration
- `core`: shared configuration, caching, and cross-cutting concerns
- `frontend`: single-page dashboard for clinician-facing review

The main design goal is to keep the critical reconciliation logic deterministic and testable, while still integrating an LLM in a controlled way.

## Request flow

### Medication reconciliation

1. Frontend submits a medication conflict payload to `POST /api/reconcile/medication`
2. FastAPI validates the payload with `Pydantic`
3. Rule-based scoring ranks the competing sources
4. The highest-scoring record becomes the selected medication
5. The local LLM optionally rewrites the explanation text
6. If the local model fails or returns invalid output, the backend falls back to the rule-based explanation
7. Frontend renders the final result, confidence, safety status, and actions

### Data quality validation

1. Frontend submits a patient record to `POST /api/validate/data-quality`
2. FastAPI validates the payload with `Pydantic`
3. Rule-based checks compute completeness, accuracy, timeliness, and clinical plausibility
4. The local LLM may propose a small number of additional issues
5. Invalid or unusable model output is discarded
6. Frontend renders the score breakdown and issue list

## Key design decisions

### FastAPI for the backend

- FastAPI was selected for fast iteration, built-in request validation, and automatic API docs.
- This makes it easy to keep route handlers thin and move logic into services.

### React + Vite + Tailwind for the frontend

- React + Vite gives a fast development loop and a familiar dashboard structure.
- Tailwind was used to satisfy the frontend stack guidance while keeping styling fast to iterate.

### Rules-first decision making

- The backend does not let the LLM choose the final medication.
- Instead, deterministic rules score source reliability, recency, and limited clinical context.
- This keeps the primary decision path explainable, testable, and resilient.

### Local open-source LLM instead of hosted API

- A local Ollama-hosted model avoids quota and billing constraints during development.
- It also keeps the project runnable offline once dependencies and the model are installed.
- The trade-off is slower inference and lower output quality compared with stronger hosted models.

### LLM as constrained enhancement

- For medication reconciliation, the LLM only rewrites `reasoning`.
- For data quality validation, the LLM can only add a small number of directly supported issues.
- This minimizes hallucination risk and prevents the model from overriding deterministic safety decisions.

### Confidence scoring model

Each medication source is scored as `reliability + recency + clinical_context_adjustment`:

- **Reliability** maps the source's declared reliability to a weight: high=1.0, medium=0.75, low=0.5, unknown=0.65.
- **Recency** assigns 1.0 for sources updated within 7 days, tapering to 0.5 for anything older than 90 days. Missing dates are treated as 365 days old.
- **Clinical context** makes a small adjustment when patient labs suggest one dose is more appropriate (e.g. +0.12 for metformin 500mg when eGFR <= 45, -0.1 for 1000mg).

The resulting composite score typically falls between ~1.15 and ~2.12 for realistic inputs. To produce a 0-1 confidence value, the score is divided by 2.2 (just above the practical maximum) and clamped to [0.35, 0.96]. The floor avoids misleadingly low confidence for reasonable inputs; the ceiling avoids implying certainty that a heuristic system cannot guarantee.

These values were hand-tuned against the assessment example payloads. With more time and access to labeled reconciliation outcomes, calibrating them empirically would be a priority.

### In-memory cache instead of persistence

- LLM responses are cached in memory to reduce repeated local inference cost and latency.
- No database was added because persistence is not required by the assessment and would increase scope.

## Trade-offs

- Skipping a database improves speed of delivery but means approve/reject decisions are not persisted.
- Using a small local model is cheaper and easier to demo, but quality can be less stable than larger hosted models.
- Strictly constraining the LLM improves safety and predictability, but limits how much nuanced reasoning the model can contribute.

## Future improvements

- richer rule coverage for more medication and data quality edge cases
- stronger structured output validation for local model responses
- persisted audit trail for approve / reject decisions
- Docker packaging and optional deployment
- better telemetry for model latency, cache hit rate, and fallback frequency
