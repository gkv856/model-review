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
│   │   ├── page.tsx                     Upload page
│   │   ├── results/[jobId]/page.tsx     Results + download
│   │   └── api/
│   │       ├── review/route.ts          POST proxy → FastAPI
│   │       ├── status/[jobId]/route.ts  GET proxy
│   │       ├── report/[jobId]/route.ts  GET JSON proxy
│   │       └── report/[jobId]/html/route.ts  GET HTML proxy
│   ├── components/
│   │   ├── DualFileUpload.tsx
│   │   ├── IssuesTable.tsx
│   │   ├── SummaryCard.tsx
│   │   ├── TierBreakdown.tsx
│   │   └── ProgressIndicator.tsx
│   ├── hooks/
│   │   ├── useReview.ts       useMutation → submits files, navigates to /results/{jobId}
│   │   ├── useJobStatus.ts    polls /status every 3s, stops at completed/failed
│   │   └── useReport.ts       fetches when enabled=true (after completion)
│   ├── lib/
│   │   ├── api.ts             ModelReviewApi class (streaming flag, SSE support)
│   │   ├── types.ts           All shared TS types
│   │   └── utils.ts           Shared utility functions
│   └── providers/
│       └── QueryProvider.tsx  React Query "use client" provider
│
└── backend/           Python FastAPI pipeline
    ├── map_parser.py          Step 0 ✅
    ├── parser.py              Step 1 ✅
    ├── structure_detector.py  Step 2 ✅
    ├── dependency_graph.py    Step 3 ✅
    ├── risk_scorer.py         Step 4 ✅
    ├── tier_assigner.py       Step 5 ✅
    ├── auto_flagger.py        Step 6 ✅
    ├── tier3_checker.py       Step 7 ✅
    ├── deduplicator.py        Step 8 ✅
    ├── enricher.py            Step 9 ✅
    ├── llm_reviewer.py        Step 10 ✅
    ├── propagator.py          Step 11 ✅
    ├── report_generator.py    Step 12 ✅
    ├── main.py                Step 13 ✅ (FastAPI wiring)
    ├── llm_provider.py        ✅ LangChain factory (Anthropic/OpenAI/Gemini)
    ├── utils.py               ✅ Shared utilities (make_issue, col_letter, chunked, parse_llm_json)
    ├── pytest.ini             asyncio_mode = auto
    ├── requirements.txt
    ├── .env.example
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

**Test suite status: 127/127 passing** (all steps complete).

Run tests: `cd backend && .venv/Scripts/pytest tests/ -v`

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

### Step 7: `tier3_checker.py` (NEXT TO BUILD)

Five deterministic rule checks for Tier 3 cells only. No LLM. Each check function returns `dict | None`.

```python
def run_tier3_checks(cells: list[dict], G: nx.DiGraph) -> list[dict]:
    issues = []
    tier3 = [c for c in cells if c.get("tier") == 3]
    for cell in tier3:
        for check_fn in RULE_CHECKS:
            result = check_fn(cell, G)
            if result:
                issues.append(result)
    return issues
```

**The five checks:**

1. `check_divide_by_zero_risk` — formula contains `/` AND any direct predecessor has `value == 0` or `value` near-zero (`abs(v) < 1e-9`). Severity: WARNING.

2. `check_hardcoded_mid_chain` — cell has at least one direct predecessor whose `symbol == "N"` AND the cell itself has at least one dependent (not a terminal node). A hardcoded value feeding into a formula chain is fragile. Severity: WARNING.

3. `check_self_reference` — cell's own `(sheet, cell)` appears in its `raw_dependencies`. Severity: CRITICAL.

4. `check_empty_sum_range` — symbol == "S" AND the cell's computed `value` is 0 or None AND all direct predecessor values are also 0 or None. May indicate summing an empty range. Severity: INFO.

5. `check_unit_mismatch_heuristic` — cell has a `units` field (from enrichment — skip if absent). If the cell's units differ from the majority units of its direct predecessors, flag it. Only run if `units` is populated. Severity: WARNING.

Use `make_issue()` from `utils.py` for all issue dicts.

**Tests to write:** One test per check function (positive + negative case each). Use `make_cell()` and `build_graph()` from conftest.

---

### Step 8: `deduplicator.py`

Two functions. Both operate only on Tier 1 + Tier 2 cells.

```python
def normalise_formula(formula: str) -> str:
    # 1. Uppercase
    # 2. Strip cross-sheet refs: 'SheetName'!A1 → XSHEET!REF
    # 3. Strip ranges: A1:B5 → RANGE
    # 4. Strip cell refs: A1 → REF
    # 5. Strip numeric constants: 0.3 → CONST
    # Returns structural pattern string

def deduplicate_by_pattern(cells: list[dict]) -> list[dict]:
    # Groups by (symbol, normalise_formula(formula))
    # Returns one representative per group: highest risk_score cell
    # Sets on representative: pattern_instances=[other cell coords], pattern_instance_count=N
    # Cells with no formula get their own group (normalised to "")
```

**Important:** Cross-sheet ref regex must handle both quoted (`'P&L'!F15`) and bare (`Sheet2!C10`) forms. Strip both before applying range/cell patterns to avoid double-matching.

**Tests:** Verify normalisation output for a few known inputs. Verify deduplication groups identical patterns. Verify representative is highest-scoring cell.

---

### Step 9: `enricher.py`

Run on deduplicated representatives only (Tier 1 + 2). Adds label, units, period, section, and dependency details. Requires the structure map from `structure_detector.py` and the `data_only=True` workbook.

```python
def enrich_cell(cell: dict, structure_map: dict, wb_values) -> dict:
    # Returns new dict merging cell + {label, units, period, section, dependencies}

def enrich_cells(cells: list[dict], structure_map: dict, wb_values) -> list[dict]:
    # Applies enrich_cell to each, returns same list (mutates in place)
```

**Label lookup:** `structure_map[sheet]["label_col"]` → read that column at cell's row. Fall back to `f"Row {row}"` if None.

**Period lookup:** `structure_map[sheet]["timeline_row"]` → read that row at cell's column. May be None.

**Section lookup:** Walk `structure_map[sheet]["section_headers"]` in reverse row order. First header with `header["row"] <= cell["row"]` is the section. Fall back to `"General"`.

**Dependencies:** For each `(dep_sheet, dep_coord)` in `raw_dependencies`, look up its label (same label_col logic) and its computed value from `wb_values[dep_sheet][dep_coord].value`.

---

### Step 10: `llm_reviewer.py`

LangChain-based async reviewer. Uses `get_llm()` from `llm_provider.py`. Operates on enriched representatives from Tiers 1 and 2.

```python
async def review_tier1(cells: list[dict]) -> list[dict]:
    # Batch size 20, grouped by sheet+section first
    # Full enriched prompt — see system prompt in PRD §Step 10

async def review_tier2(cells: list[dict]) -> list[dict]:
    # Batch size 50
    # Lightweight prompt — formula + label + symbol only

async def review_cross_section(terminal_cells: list[dict]) -> list[dict]:
    # Single call with all terminal cells
    # Checks sign flips, unit changes, missing bridges between sections

async def run_llm_review(
    tier1_reps: list[dict],
    tier2_reps: list[dict],
) -> list[dict]:
    # Orchestrates all three passes, returns combined issues list
```

**Prompts:** Define as module-level string constants, not inline. See PRD §Step 10 for exact prompt text.

**LLM call pattern:**

```python
llm = get_llm()
messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
response = await llm.ainvoke(messages)
issues = parse_llm_json(response.content)  # from utils.py
```

`parse_llm_json` in `utils.py` strips markdown fences and parses the `issues` array.

**Retry:** On exception, retry once with a 2-second wait. On second failure, log and skip batch (do not crash pipeline).

**LLM call count tracking:** Return a dict `{"issues": [...], "llm_calls": N}` or track via a counter passed in.

---

### Step 11: `propagator.py`

```python
def propagate_findings(issues: list[dict], representatives: list[dict]) -> list[dict]:
    # For each issue, find its representative cell
    # Set issue["instances"] = [issue["cell"]] + rep["pattern_instances"]
    # Set issue["instance_count"] = len(instances)
    # Return same list (mutates in place)
```

Simple lookup by `(sheet, cell)` match against the representatives list. If no match, `instances = [cell]`, `instance_count = 1`.

---

### Step 12: `report_generator.py`

```python
def build_json_report(
    job_id: str,
    model_filename: str,
    map_filename: str,
    cells: list[dict],
    issues: list[dict],
    auto_issues: list[dict],
    llm_calls_made: int,
    patterns_reviewed: int,
) -> dict:
    # Assembles the full JSON report structure per PRD §Step 12
    # summary: total_ufs, symbol_breakdown, tier_breakdown, llm_calls_made,
    #          patterns_reviewed, total_issues, critical, warning, info, cells_affected_by_issues
    # graph_analysis: circular_references, broken_references, external_links_in_chain, hardcoded_mid_chain
    # issues: combined + sorted by severity (CRITICAL → WARNING → INFO), then tier

def build_html_report(report: dict) -> str:
    # Standalone single-file HTML — NO CDN DEPENDENCIES
    # Embed all CSS inline in <style> tags
    # Embed all JS inline in <script> tags
    # Features: sortable/filterable issues table, expandable instances, collapsible graph section
    # Print-ready, neutral dark styling
```

---

### Step 13: `main.py`

FastAPI app with background task pipeline and in-memory job store.

```python
# Job states
JOB_STORE: dict[str, dict] = {}
# job = { "status": "pending"|"running"|"completed"|"failed",
#          "progress": 0-100, "step": str, "error": str|None,
#          "report": dict|None }

# Routes
POST /review          — accepts multipart (model_file, map_file), starts background task, returns {job_id}
GET  /status/{job_id} — returns {job_id, status, progress, step, error}
GET  /report/{job_id} — returns full JSON report
GET  /report/{job_id}/html — returns HTML report string

# Pipeline steps with progress %:
# 0  map_parser        5%
# 1  parser           10%
# 2  structure_detect 20%
# 3  build_graph      30%
# 4  risk_scorer      40%
# 5  tier_assigner    45%
# 6  auto_flagger     50%
# 7  tier3_checker    55%
# 8  deduplicator     60%
# 9  enricher         65%
# 10 llm_review       85%  (longest step)
# 11 propagator       90%
# 12 report_gen      100%
```

**File handling:** Save uploaded files to `tempfile.mkdtemp()`, clean up after pipeline completes or fails.

**Error handling:** Any unhandled exception in background task → set `status = "failed"`, `error = str(e)`, log traceback.

**CORS:** Allow `http://localhost:3000` in dev. Use env var `ALLOWED_ORIGINS` for prod.

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

`llm_provider.py` returns a `BaseChatModel` based on `LLM_PROVIDER` env var:

```python
from llm_provider import get_llm
llm = get_llm()                          # returns ChatAnthropic | ChatOpenAI | ChatGoogleGenerativeAI
response = await llm.ainvoke(messages)   # LangChain unified interface
```

Defaults:

- `anthropic` → `claude-sonnet-4-20250514`
- `openai` → `gpt-4o`
- `gemini` → `gemini-2.0-flash`

Override with `MODEL_NAME` env var.

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

## Backend — COMPLETE

All 13 pipeline steps implemented and tested. **127/127 tests passing.**

## What's Next

- End-to-end test with a real small model (100 UFs) + map file pair
- Set up `.env` with API keys, run `uvicorn main:app --reload --port 8000`, then `npm run dev` in frontend
- Verify frontend renders results correctly against real API responses
