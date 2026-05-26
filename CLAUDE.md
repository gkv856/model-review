# Financial Model Integrity Reviewer — Master CLAUDE.md

This is the authoritative context file for the entire mono repo. Read it fully before writing any code.

---

## Project Overview

Upload two Excel files (model + VBA map) → structured integrity review of unique formulas.

**Core design principle: graph-first, LLM-last.**
The dependency graph is the primary analysis engine. The LLM only sees high-risk cells after tiering and pattern deduplication. LLM input is always bounded regardless of total unique-formula (UF) count.

**PRD:** `PRD_Financial_Model_Reviewer_v3.md` in repo root — the authoritative spec.

---

## Repo Structure

```
model-review/
├── frontend/          Next.js 16+ App Router (dark mode, shadcn/ui v4, TanStack Query v5)
│   ├── app/
│   │   ├── page.tsx                               Upload page + previous runs list
│   │   ├── results/[jobId]/page.tsx               Full JSON report + HTML download
│   │   ├── results/[jobId]/pipeline/page.tsx      Pipeline Inspector (stage-by-stage live view)
│   │   └── api/
│   │       ├── review/route.ts                    POST proxy → FastAPI
│   │       ├── status/[jobId]/route.ts            GET proxy
│   │       ├── report/[jobId]/route.ts            GET JSON proxy
│   │       ├── report/[jobId]/html/route.ts       GET HTML proxy
│   │       ├── interim/route.ts                   GET /interim — list all past job folders
│   │       ├── interim/[jobId]/route.ts           GET /interim/{job_id} — list stage files
│   │       └── interim/[jobId]/[filename]/route.ts  GET /interim/{job_id}/{filename}
│   ├── components/
│   │   ├── DualFileUpload.tsx
│   │   ├── IssuesTable.tsx
│   │   ├── SummaryCard.tsx
│   │   ├── TierBreakdown.tsx
│   │   └── ProgressIndicator.tsx
│   ├── hooks/
│   │   ├── useReview.ts         useMutation → submits files, navigates to /results/{jobId}/pipeline
│   │   ├── useJobStatus.ts      polls /status every 3s, stops at completed/failed
│   │   ├── useReport.ts         fetches when enabled=true (after completion)
│   │   └── usePipelineData.ts   polls /interim/{jobId} every 2s, fetches each stage file once ready
│   ├── lib/
│   │   ├── api.ts               ModelReviewApi class
│   │   ├── types.ts             All shared TS types
│   │   ├── utils.ts             Shared utility functions
│   │   └── pipelineSteps.ts     Step definitions, CSV/JSON parsers, per-step aggregation logic
│   └── providers/
│       └── QueryProvider.tsx    React Query "use client" provider
│
└── backend/           Python FastAPI pipeline (refactored into logical packages)
    ├── main.py                Entry point — re-exports app from api/app.py
    ├── pytest.ini             asyncio_mode = auto, pythonpath = .
    ├── requirements.txt
    ├── .env.example
    ├── utils/                 Shared utilities
    │   ├── __init__.py        Re-exports all helpers + get_logger
    │   ├── helpers.py         make_issue, chunked, col_letter, parse_llm_json
    │   └── logger.py          get_logger() — RotatingFileHandler + console, logs/app.log
    ├── core/                  Steps 0–5: parsing, graph, scoring, tiering
    │   ├── map_parser.py      Step 0 ✅ parse_map, symbol_counts
    │   ├── model_parser.py    Step 1 ✅ parse_model
    │   ├── structure_detector.py  Step 2 ✅ detect_structure (parallel per-sheet)
    │   ├── dependency_graph.py    Step 3 ✅ build_graph (parallel node metrics)
    │   ├── risk_scorer.py         Step 4 ✅ score_cells (parallel chunks)
    │   └── tier_assigner.py       Step 5 ✅ assign_tiers
    ├── analysis/              Steps 6–9: flagging, rule checks, dedup, enrichment
    │   ├── auto_flagger.py    Step 6 ✅ auto_flag (x_in_chain, circular, broken_ref)
    │   ├── tier3_checker.py   Step 7 ✅ run_tier3_checks (5 rule checks)
    │   ├── deduplicator.py    Step 8 ✅ deduplicate_by_pattern, normalise_formula
    │   └── enricher.py        Step 9 ✅ enrich_cells (label, units, period, section)
    ├── llm/                   Steps 10: LLM provider + reviewer
    │   ├── provider.py        get_llm() — Anthropic / OpenAI / Gemini via env var
    │   └── reviewer.py        Step 10 ✅ run_llm_review (tier1, tier2, cross-section)
    ├── reporting/             Steps 11–12: propagation + report generation
    │   ├── propagator.py      Step 11 ✅ propagate_findings
    │   └── generator.py       Step 12 ✅ build_json_report, build_html_report
    ├── pipeline/              Orchestration + interim file output
    │   ├── runner.py          Full pipeline runner (called by api/routes.py)
    │   └── interim.py         Writes CSV/JSON per stage to interim/{job_id}/
    ├── api/                   FastAPI app
    │   ├── app.py             FastAPI app factory, CORS setup
    │   ├── routes.py          POST /review, GET /status, GET /report
    │   └── job_store.py       In-memory JOB_STORE dict
    └── tests/
        ├── conftest.py        make_cell(), make_graph(), make_xlsx fixture, make_wb fixture
        ├── test_map_parser.py      ✅ 8 tests
        ├── test_parser.py          ✅ 6 tests
        ├── test_structure_detector.py ✅ 9 tests
        ├── test_dependency_graph.py   ✅ 12 tests
        ├── test_risk_scorer.py        ✅ 7 tests
        ├── test_tier_assigner.py      ✅ 6 tests
        ├── test_auto_flagger.py       ✅ 12 tests
        ├── test_tier3_checker.py      ✅ 15 tests
        ├── test_deduplicator.py       ✅ 15 tests
        ├── test_enricher.py           ✅ 11 tests
        ├── test_llm_reviewer.py       ✅ 11 tests
        ├── test_propagator.py         ✅ 5 tests
        └── test_report_generator.py   ✅ 9 tests
```

**Test suite status: 127/127 passing** (all steps complete, refactored package structure).

Run tests: `cd backend && .venv/Scripts/pytest tests/ -v`

Start server: `uvicorn main:app --reload --port 8000` (or `uvicorn api.app:app --reload --port 8000`)

Interim files written per job to: `backend/outputs/interim/{job_id}/00_meta.json` … `12_propagated_issues.csv`
- `00_meta.json` written immediately on job submission (before pipeline starts) — survives backend restarts
- `11_llm_prompts.json` written after Step 10 — contains exact system prompt, user prompt, and raw LLM response per batch
Log file: `backend/logs/app.log` (RotatingFileHandler, 10MB × 5 backups)

---

## Symbol Convention (from map file)

| Symbol    | Meaning                 | Pipeline Treatment                  |
| --------- | ----------------------- | ----------------------------------- |
| `N`       | Hardcoded number        | Auto-flag INFO, no LLM              |
| `F`       | Unique formula          | Risk-score → tier → LLM if Tier 1/2 |
| `S`       | Unique sum/subtotal     | Risk-score → tier → LLM if Tier 1/2 |
| `C`       | Callup (cross-cell ref) | Risk-score → tier → LLM if Tier 1/2 |
| `X`       | External link           | Auto-flag WARNING, no LLM           |
| _(empty)_ | Dragged copy            | Skip entirely                       |

---

## Pipeline Step Details

### Steps 0–6 (DONE)

All implemented with tests. Key design facts:

- **Graph direction:** dependency → dependent (B1 feeds A1 → edge B1→A1)
- **Risk score components:** descendants×0.5 (cap 35) + terminal +20 + sheet_depth×5 (cap 15) + symbol weight S=15/F=10/C=5 + ancestors×0.2 (cap 10) + bridge +5
- **Tier thresholds:** percentile-based via np.percentile(scores, 85/50). Falls back to fixed 60/30 when std < 1e-6
- **auto_flagger.py:** Three detectors — x_in_chain (F/S/C depending on X), circular_refs (nx.simple_cycles), broken_refs (raw_dependencies not in graph nodes)

---

### Steps 7–12 (DONE)

All steps fully implemented and tested. Key implementation notes:

**Step 7 — `tier3_checker.py`:** Five deterministic rule checks for Tier 3 cells (divide-by-zero risk, hardcoded mid-chain, self-reference, empty sum range, unit mismatch heuristic). Uses `make_issue()` from `utils.py`.

**Step 8 — `deduplicator.py`:** `normalise_formula` strips cross-sheet refs (quoted + bare), ranges, cell refs, numeric constants. `deduplicate_by_pattern` groups by `(symbol, normalised_formula)`, returns highest-`risk_score` representative per group. Sets `pattern_instances` and `pattern_instance_count` on representative.

**Step 9 — `enricher.py`:** Adds `label`, `units`, `period`, `section`, `dependencies` to each representative from the structure map + `data_only=True` workbook.

**Step 10 — `llm/reviewer.py`:** Three async passes — `review_tier1` (batch 20, grouped by sheet+section), `review_tier2` (batch 50, formula+label only), `review_cross_section` (single call on terminal cells). `_call_llm_with_retry` returns `(issues, raw_response_text)`. Each batch produces a prompt record written to `11_llm_prompts.json` containing `system_prompt`, `user_prompt`, and `raw_response`. `run_llm_review` returns `{"issues": [...], "llm_calls": N, "prompts": [...]}`.

**Step 11 — `reporting/propagator.py`:** `propagate_findings` sets `instance_count` on each issue by looking up its representative's `pattern_instances`.

**Step 12 — `reporting/generator.py`:** `build_json_report` assembles the full structured report. `build_html_report` produces a standalone single-file HTML with no CDN dependencies.

**API (`api/routes.py`):** In addition to the core routes, three `/interim` endpoints serve stage files without requiring JOB_STORE (works after backend restart):
- `GET /interim` — lists all job folders, reads `00_meta.json` for model filename + start time
- `GET /interim/{job_id}` — lists stage files with sizes
- `GET /interim/{job_id}/{filename}` — serves a single CSV or JSON file

`write_metadata(job_id, ...)` is called immediately at submission before the background task starts, so `00_meta.json` always exists even for failed/incomplete jobs.

---

## Frontend Conventions (GKV Style)

From `.claude/gkv-coding-style.md`:

- **Interface props pattern:** All functions with multiple params take a single props object. Destructure in body.
- **Interface naming:** `I` prefix, max 15 chars (e.g. `IApiConfig`, `ISubmitReview`, `IJobId`)
- **No emoji in logs.** Format: `[ServiceName] message`, then a data object on next line
- **One statement per line.** Pre-create objects for console.log calls
- **Comments:** Document function input/output at top. Explain complex blocks. No obvious comments.
- **File naming:** PascalCase.tsx for components/pages, camelCase.ts for hooks/utils
- **Prompts:** Module-level string constants, never inline

**Next.js 16 specifics:**

- `params` is `Promise<{...}>` — unwrap with `use(params)` (React hook) in client components
- Route handlers: use `RouteContext<"/api/path/[param]">` for typed params
- App Router only, no pages directory

**Tailwind v4:**

- CSS-based config via `@import "tailwindcss"` in globals.css
- No `tailwind.config.ts` needed

**Dark mode:**

- All `:root` CSS variables set to dark values in `globals.css`
- `<html className="... dark">` in `layout.tsx`
- No light/dark toggle — forced dark

---

## Backend Conventions

- **DRY:** Shared utilities live in `utils.py`. Import from there, never duplicate.
- **`make_issue()`** — always use this factory for issue dicts. All params keyword-only.
- **`chunked(lst, size)`** — use this for batching LLM calls. In `utils.py`.
- **`parse_llm_json(text)`** — strips markdown fences, parses `issues` key. In `utils.py`.
- **`col_letter(idx)`** — wraps `get_column_letter`. In `utils.py`.
- **Tests:** Every module gets its own `tests/test_<module>.py`. Use `make_cell()` and `make_graph()` from conftest. Tests must pass before moving to next step.
- **No single-provider LLM lock-in.** Always call `get_llm()` from `llm_provider.py`. Never import ChatAnthropic/ChatOpenAI directly in pipeline modules.
- **Async LLM calls:** Use `await llm.ainvoke(messages)`. FastAPI background tasks run in thread, wrap with `asyncio.run()` or use `asyncio.get_event_loop()`.

---

## LLM Provider Setup

`llm/provider.py` returns a `BaseChatModel` based on `LLM_PROVIDER` env var. Supported values: `anthropic`, `openai`, `azure`, `gemini`, `ollama`.

```python
from llm_provider import get_llm
llm = get_llm()                          # returns ChatAnthropic | ChatOpenAI | ChatGoogleGenerativeAI
response = await llm.ainvoke(messages)   # LangChain unified interface
```

Defaults:

- `anthropic` → `claude-sonnet-4-20250514`
- `openai`    → `gpt-4o`
- `azure`     → `gpt-4o` (set `MODEL_NAME` to your deployment name)
- `gemini`    → `gemini-2.0-flash`
- `ollama`    → `gemma3:12b`

For `azure`, three additional env vars are required: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`. Uses `AzureChatOpenAI` from `langchain-openai` (no extra package needed). `MODEL_NAME` maps to `azure_deployment`.

Override model with `MODEL_NAME` env var.

---

## Environment Setup

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate         # Windows
pip install -r requirements.txt
cp .env.example .env           # fill in your API key
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                    # http://localhost:3000
```

**Frontend calls backend through Next.js API proxy routes** (`/api/*` → `http://localhost:8000/*`).
Never call the FastAPI server directly from browser components.

---

## Known Issues / Gotchas

1. **LangChain version pinning:** Use `>=` ranges in requirements.txt, not exact pins. `langchain-anthropic` requires `langchain-core>=0.3.30` which conflicts with exact `==0.3.29`.

2. **Graph edge direction:** Edge goes from dependency TO dependent. `A1 = B1 + C1` → edges `B1→A1` and `C1→A1`. `is_terminal` means no outgoing edges (nothing depends on it = it's an output cell).

3. **Range expansion cap:** `MAX_RANGE_CELLS = 200` in `dependency_graph.py`. Prevents memory explosion from giant ranges like `SUM(A1:A10000)`.

4. **Cross-sheet regex order:** In `extract_refs`, strip cross-sheet refs before extracting same-sheet refs to avoid double-counting coords that appear in both.

5. **Tier 3 "flat distribution" fallback:** When `score_arr.std() < 1e-6`, use `_FALLBACK_TIER1=60.0` and `_FALLBACK_TIER2=30.0`. This prevents a divide-by-zero in percentile logic when all scores are identical.

6. **Next.js 16 async params:** In server components: `const { jobId } = await ctx.params`. In client components: `const { jobId } = use(params)` (React `use` hook).

7. **shadcn/ui v4:** Init with `npx shadcn@latest init --yes --defaults --no-monorepo`. No `--base-color` flag (removed in v4). Components live in `frontend/components/ui/`.

---

## Status — COMPLETE

**Backend:** All 13 pipeline steps implemented and tested. **127/127 tests passing.**

**Frontend:** Fully functional.
- Upload page with previous runs list (reads `00_meta.json` from each job folder)
- Pipeline Inspector (`/results/[jobId]/pipeline`) — two-column layout, live stage-by-stage view, executive summary panel, per-step explanation toggles, real-time progress bar driven by `status.progress`, independent left/right scroll regions
- Step 11 detail panel has a dedicated "LLM Prompts" tab showing system prompt, user prompt, and raw LLM response per batch
- Full report page (`/results/[jobId]`) with JSON download and HTML report
- After submission, navigates directly to Pipeline Inspector
