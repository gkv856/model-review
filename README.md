# Financial Model Integrity Reviewer

Upload two Excel files — a financial model and a symbol map — and get a structured integrity review of every unique formula. The pipeline uses a dependency graph to rank risk, then sends only the highest-risk formula patterns to an LLM for mathematical review.

**Graph-first, LLM-last.** The LLM sees a bounded set of deduplicated patterns regardless of model size.

---

## How it works

```
Map file (.xlsx)  ──┐
                    ├──► Parse ──► Build graph ──► Score & tier ──► Deduplicate ──► Enrich ──► LLM review ──► Report
Model file (.xlsx) ─┘
```

| Step | What happens                                                                                                  |
| ---- | ------------------------------------------------------------------------------------------------------------- |
| 0    | Map file parsed — builds whitelist of cells and their symbols (F/S/C/N/X)                                     |
| 1    | Model file parsed — reads formulas and computed values for whitelisted cells                                  |
| 2    | Structure detected — finds timeline row, label column, section headers per sheet                              |
| 3    | Dependency graph built — networkx DiGraph, node metrics computed in parallel                                  |
| 4    | Risk scored — 6-component score (0–100) per cell, parallel chunks                                             |
| 5    | Tiers assigned — percentile-based: Tier 1 (top 15%), Tier 2 (mid 35%), Tier 3 (bottom 50%)                    |
| 6    | Auto-flagged — X-in-chain, circular refs, broken refs (no LLM)                                                |
| 7    | Tier 3 rule checks — divide-by-zero risk, self-reference, empty sums, hardcoded mid-chain, unit mismatch      |
| 8    | Deduplicated — structurally identical formulas collapsed to one representative per pattern                    |
| 9    | Enriched — label, units, period, section, dependency values added to each representative                      |
| 10   | LLM review — Tier 1 (full context, batches of 20) + Tier 2 (lightweight, batches of 50) + cross-section pass |
| 11   | Propagated — findings on a representative applied to all cells sharing the same pattern                       |
| 12   | Report — JSON + standalone HTML with filterable issues table                                                  |

---

## Symbol convention

| Symbol | Meaning                 | Pipeline treatment                  |
| ------ | ----------------------- | ----------------------------------- |
| `F`    | Unique formula          | Risk score → tier → LLM if Tier 1/2 |
| `S`    | Unique sum/subtotal     | Risk score → tier → LLM if Tier 1/2 |
| `C`    | Callup (cross-cell ref) | Risk score → tier → LLM if Tier 1/2 |
| `N`    | Hardcoded number        | Auto-flag INFO, no LLM              |
| `X`    | External link           | Auto-flag WARNING, no LLM           |

---

## Repo structure

```
model-review/
├── backend/                    Python FastAPI pipeline
│   ├── main.py                 Entry point (uvicorn main:app)
│   ├── utils/                  Shared utilities + logger
│   ├── core/                   Steps 0–5: parsing, graph, scoring, tiering
│   ├── analysis/               Steps 6–9: flagging, rule checks, dedup, enrichment
│   ├── llm/                    Step 10: LLM provider + reviewer
│   ├── reporting/              Steps 11–12: propagation + report generation
│   ├── pipeline/               Orchestration + interim file output per stage
│   ├── api/                    FastAPI app, routes, in-memory job store
│   ├── outputs/interim/        Stage-by-stage output files, one folder per job
│   ├── tests/                  127 tests, all passing
│   ├── .env.example            Copy to .env and configure
│   └── requirements.txt
│
└── frontend/                   Next.js 16+ App Router
    ├── app/
    │   ├── page.tsx                        Upload page + previous runs list
    │   ├── results/[jobId]/page.tsx        Full JSON report + HTML download
    │   ├── results/[jobId]/pipeline/       Pipeline Inspector (stage-by-stage)
    │   └── api/                            Next.js proxy routes → FastAPI
    │       ├── review/route.ts
    │       ├── status/[jobId]/route.ts
    │       ├── report/[jobId]/route.ts
    │       ├── report/[jobId]/html/route.ts
    │       ├── interim/route.ts            Lists all past job folders
    │       ├── interim/[jobId]/route.ts    Lists stage files for a job
    │       └── interim/[jobId]/[filename]/ Downloads a single stage file
    ├── components/             DualFileUpload, IssuesTable, SummaryCard, etc.
    ├── hooks/                  useReview, useJobStatus, useReport, usePipelineData
    └── lib/                    api.ts, types.ts, utils.ts, pipelineSteps.ts
```

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- One of: [Ollama](https://ollama.com) (local, default) · Anthropic API key · OpenAI API key · Google API key

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

cp .env.example .env            # default: LLM_PROVIDER=ollama, MODEL_NAME=gemma3:12b
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

Open [http://localhost:3000](http://localhost:3000), upload your model and map files. After submission you land directly on the **Pipeline Inspector** — a live stage-by-stage view that unlocks each step as its output file lands on disk.

---

## LLM providers

Set `LLM_PROVIDER` in `backend/.env`. No restart needed between jobs — the provider is read per-request.

| Provider       | `LLM_PROVIDER` | Default model              | API key required    |
| -------------- | -------------- | -------------------------- | ------------------- |
| Ollama (local) | `ollama`       | `gemma3:12b`               | No                  |
| Anthropic      | `anthropic`    | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI         | `openai`       | `gpt-4o`                   | `OPENAI_API_KEY`    |
| Google Gemini  | `gemini`       | `gemini-2.0-flash`         | `GOOGLE_API_KEY`    |

Override the model with `MODEL_NAME=gemma3:27b` (or any model from `ollama list`).

### Ollama setup

```bash
ollama pull gemma3:12b          # or whichever model you want
# Ollama serves on http://localhost:11434 by default
```

---

## API endpoints

| Method | Path                              | Description                                                       |
| ------ | --------------------------------- | ----------------------------------------------------------------- |
| `POST` | `/review`                         | Upload `model_file` + `map_file` (multipart), returns `{job_id}` |
| `GET`  | `/status/{job_id}`                | Poll progress: status, progress %, current step                   |
| `GET`  | `/report/{job_id}`                | Full JSON report (job must be completed)                          |
| `GET`  | `/report/{job_id}/html`           | Standalone HTML report                                            |
| `GET`  | `/interim`                        | List all past job folders with metadata                           |
| `GET`  | `/interim/{job_id}`               | List stage files available for a job                              |
| `GET`  | `/interim/{job_id}/{filename}`    | Download a single stage file (CSV or JSON)                        |
| `GET`  | `/health`                         | Health check                                                      |

---

## Interim files

Every pipeline run writes human-readable stage outputs to `backend/outputs/interim/{job_id}/`:

```
00_meta.json              — job metadata (model filename, start time)
01_map_parsed.csv
02_cells_parsed.csv
03_structure_map.json
04_graph_metrics.csv
05_cells_scored.csv
06_cells_tiered.csv
07_auto_flags.csv
08_tier3_issues.csv
09_deduplication.csv
10_cells_enriched.csv
11_llm_issues.csv
11_llm_prompts.json       — exact system + user prompts and raw LLM responses per batch
12_propagated_issues.csv
```

These files persist across backend restarts and are served by the Pipeline Inspector. Past runs are listed on both the home page and the pipeline inspector's run selector.

---

## Running tests

```bash
cd backend
.venv\Scripts\pytest tests/ -v
# 127/127 passing
```
