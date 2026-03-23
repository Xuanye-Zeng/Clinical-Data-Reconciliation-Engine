# Clinical Data Reconciliation Engine

A mini full-stack app that reconciles conflicting medication records across healthcare systems, scores patient data quality, and presents the results in a clinician-facing dashboard.

Built for the Full Stack Developer - EHR Integration Intern take-home assessment.

## Quick start

### 1. Ollama (local LLM)

```bash
brew install ollama
brew services start ollama
ollama pull qwen2.5:1.5b
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Runs at `http://127.0.0.1:8000`. Swagger docs at `/docs`, health check at `/health`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Runs at `http://127.0.0.1:5173`.

### 4. Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Design approach

The most important decision I made was keeping the LLM out of the decision loop. In a clinical reconciliation system, the thing that picks the "most likely truth" medication and flags safety issues needs to be deterministic and testable -- you can't have an LLM occasionally hallucinate a dosage. So I built a rule engine that scores each medication source by reliability, recency, and basic clinical context (e.g. preferring a lower metformin dose when eGFR indicates reduced kidney function), and that engine is always the source of truth for the selected medication, the confidence score, and the safety check.

The LLM's only job is to make the output more readable. For reconciliation, it rewrites the rule engine's explanation in clearer clinician-friendly language. For data quality, it can suggest up to two additional issues that the rules didn't catch, as long as those issues are directly supported by the payload. If the model is slow, returns garbage, or drifts away from the selected medication, the backend silently falls back to the rule-based output. This means the app works fine even when Ollama is down.

I went with a local model (`qwen2.5:1.5b` via Ollama) instead of OpenAI or Anthropic so the project runs without API keys or billing. The trade-off is noticeably lower output quality and slower first inference (the model has to load into memory), but for a take-home demo where the LLM is an enhancement layer rather than the core logic, I thought this was the right call.

Prompts are structured as JSON payloads with explicit constraints (`must_preserve_selected_medication`, `must_not_change_safety_check`, etc.) rather than free-form instructions. The backend validates LLM output before applying it -- checking length bounds, verifying the winning source name appears in the reasoning, and rejecting anything that doesn't parse as the expected JSON shape. I found this was necessary because smaller models often drift outside the requested format.

## How confidence scoring works

Each medication source gets a composite score from three factors:

- **Reliability weight** -- "high" sources get 1.0, "medium" 0.75, "low" 0.5. Unknown values default to 0.65 so the system doesn't break on unexpected input.
- **Recency** -- sources updated within 7 days score 1.0, tapering to 0.5 for anything older than 90 days. Undated sources are treated as a year old.
- **Clinical context** -- a small adjustment for cases where the patient's lab values suggest one dose is more clinically appropriate (e.g. +0.12 for metformin 500mg when eGFR is low, -0.1 for 1000mg in the same situation).

The raw composite score (reliability + recency + adjustment) ranges roughly from 1.15 to 2.12 for typical inputs. To map this to a 0-1 confidence range, I divide by 2.2 and clamp between 0.35 and 0.96. The floor of 0.35 prevents reporting misleadingly low confidence for reasonable inputs, and the ceiling of 0.96 avoids implying certainty that a rule-based system can't guarantee. These thresholds are heuristic -- with more time I'd calibrate them against labeled reconciliation outcomes.

## Key trade-offs

- **No database.** Approve/reject decisions in the UI are session-only and not persisted. I skipped persistence to keep scope focused on the reconciliation logic and AI integration. The approve/reject buttons are there to satisfy the UI requirement, but the dashboard makes it clear that decisions are recorded for the current session only.
- **Local model vs. hosted.** Cheaper and easier to demo, but output quality is less stable and first inference can take several seconds.
- **LLM strictly constrained.** Safer and more predictable, but limits how much nuance the model can contribute to explanations.

## What I'd do differently with more time

The confidence formula is the area I'm least satisfied with. The weights and thresholds were hand-tuned to produce reasonable outputs for the example payloads, but I'd want to validate them against a labeled dataset of real reconciliation decisions. I'd also want to add more clinical plausibility rules -- right now the system only checks metformin against eGFR, but a production version would need drug-disease interaction checks, contraindication lookups, and cross-field consistency rules.

On the frontend side, I'd add a side-by-side source comparison view so clinicians can see exactly which records conflict and why the engine chose what it chose. The loading and error states could also be more informative -- right now a slow LLM inference just shows "Reconciling..." with no progress indicator.

Other things on the list: Docker packaging for easier setup, better telemetry around LLM latency and fallback frequency, and stricter structured output validation (especially for the data quality issue generation path where the model occasionally returns issues that aren't well-supported by the payload).

## Estimated time spent

Around 14 hours spread over 3 days -- roughly 6 on the backend (rule engine, LLM integration, prompt tuning), 4 on the frontend (dashboard layout, result rendering, demo payloads), 2 on testing and debugging, and 2 on documentation and cleanup.

## Tech stack

- **Backend:** Python, FastAPI, Pydantic, httpx
- **Frontend:** React, Vite, Tailwind CSS
- **Testing:** pytest
- **LLM:** Ollama + qwen2.5:1.5b

## Project structure

- `backend/` -- FastAPI app, rule engine, LLM integration, tests
- `frontend/` -- React dashboard and API client
- `docs/` -- architecture notes

## Environment variables

See `backend/.env.example` and `frontend/.env.example` for all available settings. The main ones:

- `APP_API_KEY` -- shared secret for the `x-api-key` header (default: `demo-key`)
- `OLLAMA_BASE_URL` / `OLLAMA_MODEL` -- point at your Ollama instance
- `VITE_API_BASE_URL` / `VITE_APP_API_KEY` -- frontend connects to the backend

## Notes

- The first local inference can be noticeably slow while the model loads into memory. Subsequent calls are faster and benefit from in-memory caching.
- If Ollama is not running, the app still works -- you just get the rule-based output without LLM-enhanced explanations.
