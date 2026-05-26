# PRD: Financial Model Integrity Reviewer
**Version:** 3.0  
**Stack:** Next.js (frontend) + Python FastAPI (backend) + Claude API (LLM)  
**Scope:** Upload an Excel financial model + VBA map file → structured integrity review on unique formulas only  
**Scale:** Designed to handle any UF count — 100 to 20,000+

---

## 1. Problem Statement

Financial models can contain 5,000–20,000+ unique formulas (UFs). Sending all of them to an LLM is not viable — context limits, cost, and latency make it impractical. The solution is to extract maximum signal from graph analysis and rule-based checks before any LLM call, and when the LLM is invoked, send only what it uniquely adds value to.

The VBA map file identifies which cells are unique. The dependency graph identifies which of those unique cells are high-risk. The LLM only sees the high-risk cells — and even then, only after deduplication by formula pattern.

---

## 2. Map File — Symbol Convention

The map file is an `.xlsx` with identical sheet names and cell addresses as the model file.

| Symbol | Meaning | Pipeline Treatment |
|--------|---------|-------------------|
| `N` | Hardcoded number | Auto-flag, no LLM |
| `F` | Unique formula | Risk-scored → tier-assigned → LLM if Tier 1 or 2 |
| `S` | Unique sum / subtotal | Risk-scored → tier-assigned → LLM if Tier 1 or 2 |
| `C` | Callup (cross-cell reference) | Risk-scored → tier-assigned → LLM if Tier 1 or 2 |
| `X` | External link | Auto-flag, no LLM |
| *(empty)* | Dragged copy | Skip entirely |

Map file is produced by a validated EY VBA tool. Treat as ground truth — do not re-derive or validate it.

---

## 3. Core Design Principle

**Graph-first, LLM-last.**

The dependency graph is not a supporting step — it is the primary analysis engine. It scores every UF by propagation risk before any LLM call is made. The LLM is a final-layer reviewer for high-risk cells only, not a general-purpose formula scanner.

**At no point does the LLM receive all UFs.** LLM input is always bounded by the tiering + deduplication layers, regardless of total UF count.

---

## 4. Architecture Overview

```
[User Browser]
     |
     |  Upload model.xlsx + map.xlsx
     v
[Next.js Frontend]
     |
     |  POST /api/review (multipart, 2 files)
     v
[Python FastAPI Backend]
     |
     |-- Step 0: Parse Map File -> whitelist {sheet, cell, symbol}
     |-- Step 1: Parse Model File (whitelist cells only)
     |-- Step 2: Structure Detection (label/unit/timeline/section per sheet)
     |-- Step 3: Build Full Dependency Graph
     |-- Step 4: Risk Scoring (score every F/S/C cell)
     |-- Step 5: Tier Assignment (Tier 1 / 2 / 3)
     |-- Step 6: Auto-Flag (N, X, graph errors — no LLM)
     |-- Step 7: Tier 3 Rule-Based Checks (no LLM)
     |-- Step 8: Formula Pattern Deduplication (Tier 1 + 2)
     |-- Step 9: Context Enrichment (deduplicated representatives only)
     |-- Step 10: Agentic LLM Review (bounded, tiered, batched)
     |-- Step 11: Result Propagation (apply pattern findings back to all instances)
     |-- Step 12: Report Generation
     |
     v
[Next.js Frontend — results + download]
```

---

## 5. Frontend Specification (Next.js)

### 5.1 Tech Stack
- Next.js 14+ (App Router)
- TailwindCSS
- shadcn/ui
- React Query (polling)

### 5.2 Pages

#### `/` — Upload Page
- Two dropzones: "Model File (.xlsx)" and "Map File (.xlsx)"
- Both required before "Analyse" button activates
- Show filename + size on selection
- On submit: POST both files as `multipart/form-data`
- Transition to results page, poll `/api/status/{job_id}` every 3s
- Show live progress: current pipeline step + % complete

**Validation:**
- Both files must be `.xlsx`
- Max 50MB per file
- Clear error if only one uploaded

#### `/results/[jobId]` — Results Page

**Summary Card:**
- Total UFs in map
- Tier breakdown: Tier 1 / Tier 2 / Tier 3 / Auto-flagged counts
- LLM calls made (transparency)
- Issues: CRITICAL / WARNING / INFO counts

**Issues Table columns:**
`Sheet | Cell | Label | Symbol | Tier | Period | Issue Type | Severity | Description | Suggested Fix | Instances`

- `Instances` column: if a finding was applied to multiple cells sharing the same formula pattern, show count with expandable list of cell addresses

**Filter controls:**
- Tier tabs: All | Tier 1 | Tier 2 | Tier 3 | Auto-flagged
- Severity: All | Critical | Warning | Info
- Symbol: All | F | S | C | N | X
- Sheet dropdown

**Download:** JSON Report + HTML Report

### 5.3 API Proxy Routes
```
POST /api/review
GET  /api/status/{job_id}
GET  /api/report/{job_id}
GET  /api/report/{job_id}/html
```

---

## 6. Backend Pipeline

### Step 0: Map File Parser

**File:** `map_parser.py`

```python
VALID_SYMBOLS = {"N", "F", "S", "X", "C"}

def parse_map(map_path: str) -> dict:
    """
    Returns: { sheet_name: { cell_coord: symbol } }
    Example: { "P&L": { "F15": "F", "G20": "S", "D8": "N" } }
    """
    wb = openpyxl.load_workbook(map_path, data_only=True)
    whitelist = {}
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        whitelist[sheet] = {}
        for row in ws.iter_rows():
            for cell in row:
                if cell.value in VALID_SYMBOLS:
                    whitelist[sheet][cell.coordinate] = cell.value
    return whitelist
```

**Validation:**
- Total symbols = 0 → abort: "Map file appears empty or invalid"
- Sheet in map not in model → warn, skip, note in report
- Log symbol count per sheet

---

### Step 1: Model File Parser

**File:** `parser.py`

Load twice: `data_only=False` (formulas) and `data_only=True` (values).
Extract whitelist cells only.

```python
def parse_model(model_path: str, whitelist: dict) -> list[dict]:
    wb_f = openpyxl.load_workbook(model_path, data_only=False)
    wb_v = openpyxl.load_workbook(model_path, data_only=True)
    cells = []

    for sheet, cell_map in whitelist.items():
        if sheet not in wb_f.sheetnames:
            continue
        ws_f = wb_f[sheet]
        ws_v = wb_v[sheet]

        for coord, symbol in cell_map.items():
            cf = ws_f[coord]
            cv = ws_v[coord]
            formula_str = str(cf.value) if cf.value is not None else None
            cells.append({
                "sheet":      sheet,
                "cell":       coord,
                "row":        cf.row,
                "col":        cf.column,
                "symbol":     symbol,
                "formula":    formula_str,
                "value":      cv.value,
                "is_formula": bool(formula_str and formula_str.startswith("="))
            })
    return cells
```

---

### Step 2: Structure Detection

**File:** `structure_detector.py`

Run on full sheets (not just whitelist) to build layout map. Used only for enrichment context in Step 9.

Per sheet, detect:

**Timeline Row:** Scan first 10 rows. Row where >50% of non-empty cells are year integers (2015–2045), date objects, or strings matching `FY\d{4}`, `CY\d{4}`, `Q[1-4]`, `H[12]`, `\d{4}[EAF]`.

**Label Column:** Scan cols A–F. Column where >60% of cells in rows 5–200 are non-empty strings.

**Unit Column:** Column right of label col where >30% of cells contain unit strings: `USD`, `mn`, `bn`, `%`, `x`, `INR`, `days`, `#`, `bps`, `GBP`, `EUR`, `AUD`, `k`.

**Section Headers:** Rows where a single string cell exists and >80% of other cells are empty, or merged cell spans >3 columns.

**Output per sheet:**
```python
{
    "sheet":           "P&L",
    "timeline_row":    5,
    "label_col":       "D",
    "unit_col":        "E",
    "data_start_col":  "F",
    "section_headers": [
        {"row": 8,  "label": "Revenue Build"},
        {"row": 20, "label": "Cost Structure"},
        {"row": 35, "label": "EBITDA Bridge"}
    ]
}
```

---

### Step 3: Build Full Dependency Graph

**File:** `dependency_graph.py`

Build `networkx.DiGraph`. Node = `(sheet, cell)`. Edge = dependency direction (source → dependent).

**Reference extraction:**
```python
import re

def extract_refs(formula: str, current_sheet: str) -> list[tuple[str, str]]:
    refs = []
    # Cross-sheet: 'Sheet Name'!A1 or SheetName!A1
    cross = re.findall(r"'?([^'!\n]+)'?!\$?([A-Z]+)\$?(\d+)", formula)
    refs += [(s.strip("'"), f"{c}{r}") for s, c, r in cross]
    # Range expansion: A1:A10 -> A1, A2, ... A10 (same sheet)
    ranges = re.findall(r"(?<!!)\b([A-Z]+)(\d+):([A-Z]+)(\d+)\b", formula)
    for c1, r1, c2, r2 in ranges:
        refs += expand_range(current_sheet, c1, int(r1), c2, int(r2))
    # Single same-sheet refs
    same = re.findall(r"(?<!!)\b([A-Z]+\d+)\b", formula)
    refs += [(current_sheet, c) for c in same]
    return list(set(refs))  # deduplicate
```

Store `raw_dependencies: list[tuple[sheet, cell]]` on each cell dict.

Build graph and compute per-node metrics:
```python
for node in G.nodes():
    G.nodes[node]["out_degree"]   = G.out_degree(node)   # how many cells depend on this
    G.nodes[node]["in_degree"]    = G.in_degree(node)    # how many cells this depends on
    G.nodes[node]["is_terminal"]  = G.out_degree(node) == 0  # no dependents = output node
    G.nodes[node]["sheet_depth"]  = count_distinct_sheets_in_ancestors(G, node)
    G.nodes[node]["ancestors"]    = len(nx.ancestors(G, node))
    G.nodes[node]["descendants"]  = len(nx.descendants(G, node))
```

---

### Step 4: Risk Scoring

**File:** `risk_scorer.py`

Score every F, S, C cell on a 0–100 scale. N and X cells skip scoring (handled by auto-flagger).

#### Scoring Dimensions

```python
def score_cell(cell: dict, G: nx.DiGraph) -> float:
    node = (cell["sheet"], cell["cell"])
    attrs = G.nodes.get(node, {})

    score = 0.0

    # 1. Propagation risk (0-35 pts)
    # How many cells does an error here contaminate?
    descendants = attrs.get("descendants", 0)
    score += min(35, descendants * 0.5)

    # 2. Terminal output penalty (0-20 pts)
    # Output cells must be correct — errors here are the model's final answer
    if attrs.get("is_terminal"):
        score += 20

    # 3. Cross-sheet complexity (0-15 pts)
    sheet_depth = attrs.get("sheet_depth", 1)
    score += min(15, (sheet_depth - 1) * 5)

    # 4. Symbol weight (0-15 pts)
    # Aggregations (S) fail more commonly than formulas (F) or callups (C)
    symbol_weights = {"S": 15, "F": 10, "C": 5}
    score += symbol_weights.get(cell["symbol"], 0)

    # 5. Ancestor depth (0-10 pts)
    # Cell deep in a chain — error is harder to trace
    ancestors = attrs.get("ancestors", 0)
    score += min(10, ancestors * 0.2)

    # 6. Cross-section bridge (0-5 pts)
    # Cell that connects two sections — structural pivot
    if is_cross_section_bridge(cell, G):
        score += 5

    return round(score, 2)
```

Store `risk_score: float` on each cell dict.

---

### Step 5: Tier Assignment

**File:** `tier_assigner.py`

Assign every F, S, C cell to a tier based on risk score.

**Thresholds are dynamic, not fixed.**

Do not use hardcoded score cutoffs. Instead, use percentile-based thresholds computed from the actual score distribution of the model being reviewed. This ensures tier sizes are proportional regardless of model size.

```python
def assign_tiers(cells: list[dict]) -> list[dict]:
    scored = [c for c in cells if c["symbol"] in ("F", "S", "C")]
    scores = [c["risk_score"] for c in scored]

    # Tier 1: top 15th percentile — critical path cells
    # Tier 2: 15th to 50th percentile — standard formulas
    # Tier 3: bottom 50th percentile — low-risk cells
    t1_threshold = np.percentile(scores, 85)
    t2_threshold = np.percentile(scores, 50)

    for cell in scored:
        if cell["risk_score"] >= t1_threshold:
            cell["tier"] = 1
        elif cell["risk_score"] >= t2_threshold:
            cell["tier"] = 2
        else:
            cell["tier"] = 3

    return cells
```

**Expected tier distribution for a 20,000 UF model:**

| Tier | Percentile | Expected Count | LLM Treatment |
|------|-----------|----------------|---------------|
| Tier 1 | Top 15% | ~3,000 | Full enriched LLM review after pattern dedup |
| Tier 2 | 15–50% | ~7,000 | Lightweight LLM review after pattern dedup |
| Tier 3 | Bottom 50% | ~10,000 | Rule-based only, zero LLM |
| Auto-flagged (N+X) | — | Variable | Deterministic, zero LLM |

**Even with 3,000 Tier 1 cells, pattern deduplication in Step 8 reduces actual LLM input to a fraction of that — see Step 8.**

---

### Step 6: Auto-Flag (N, X, Graph Errors)

**File:** `auto_flagger.py`

Deterministic rules. No LLM.

#### N and X cells
```python
def auto_flag_symbols(cells: list[dict]) -> list[dict]:
    issues = []
    for cell in cells:
        if cell["symbol"] == "N":
            issues.append({
                "sheet": cell["sheet"], "cell": cell["cell"],
                "symbol": "N", "tier": "AUTO",
                "issue_type": "HARDCODED_INPUT", "severity": "INFO",
                "description": f"Hardcoded value ({cell['value']}) at {cell['cell']}. Verify this is intentional and not an overwritten formula.",
                "suggested_fix": "If intentional, label clearly as an assumption input.",
                "instances": [cell["cell"]]
            })
        elif cell["symbol"] == "X":
            issues.append({
                "sheet": cell["sheet"], "cell": cell["cell"],
                "symbol": "X", "tier": "AUTO",
                "issue_type": "EXTERNAL_LINK_RISK", "severity": "WARNING",
                "description": f"Cell {cell['cell']} references an external workbook. Will break if source is moved.",
                "suggested_fix": "Replace with hardcoded value on assumptions tab or internal reference.",
                "instances": [cell["cell"]]
            })
    return issues
```

#### Graph Error Auto-Flags
```python
def auto_flag_graph(G: nx.DiGraph, whitelist_cells: list[dict]) -> list[dict]:
    issues = []

    # Circular references
    try:
        cycle = nx.find_cycle(G)
        issues.append({
            "issue_type": "CIRCULAR_REFERENCE", "severity": "CRITICAL",
            "description": f"Circular reference detected: {' -> '.join(str(n) for n in cycle)}",
            "instances": [str(n) for n in cycle]
        })
    except nx.NetworkXNoCycle:
        pass

    # Broken references
    for cell in whitelist_cells:
        for dep_sheet, dep_coord in cell.get("raw_dependencies", []):
            if dep_sheet not in [c["sheet"] for c in whitelist_cells]:
                continue  # cross to non-whitelisted sheet, expected
            dep_exists = any(
                c["sheet"] == dep_sheet and c["cell"] == dep_coord
                for c in whitelist_cells
            )
            # Also check if it exists in model at all (not just whitelist)
            # Pass wb_values reference to check non-whitelist cells too
            if not dep_exists:
                issues.append({
                    "sheet": cell["sheet"], "cell": cell["cell"],
                    "issue_type": "BROKEN_REFERENCE", "severity": "CRITICAL",
                    "description": f"Formula in {cell['cell']} references {dep_sheet}!{dep_coord} which does not exist.",
                    "suggested_fix": "Check if referenced cell was deleted or moved.",
                    "instances": [cell["cell"]]
                })

    # X cell in dependency chain of F/S cell
    x_cells = {(c["sheet"], c["cell"]) for c in whitelist_cells if c["symbol"] == "X"}
    for cell in whitelist_cells:
        if cell["symbol"] not in ("F", "S"):
            continue
        node = (cell["sheet"], cell["cell"])
        ancestors = nx.ancestors(G, node) if node in G else set()
        x_ancestors = ancestors.intersection(x_cells)
        if x_ancestors:
            issues.append({
                "sheet": cell["sheet"], "cell": cell["cell"],
                "issue_type": "EXTERNAL_LINK_IN_CHAIN", "severity": "WARNING",
                "description": f"Formula at {cell['cell']} depends on external link cell(s): {x_ancestors}.",
                "instances": [cell["cell"]]
            })

    return issues
```

---

### Step 7: Tier 3 Rule-Based Checks

**File:** `tier3_checker.py`

Tier 3 cells receive no LLM review. Apply fast deterministic checks only.

```python
RULE_CHECKS = [
    check_divide_by_zero_risk,     # formula has division, denominator cell value is 0 or near-0
    check_hardcoded_mid_chain,     # N cell is a direct dependency of this F/S cell
    check_unit_mismatch_heuristic, # cell units (from unit_col) differ from all dependency units
    check_self_reference,          # formula references its own cell
    check_empty_sum_range,         # S cell sums a range where all values are 0 or empty
]

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

---

### Step 8: Formula Pattern Deduplication

**File:** `deduplicator.py`

This is the step that makes LLM review tractable regardless of UF count.

**Core idea:** Many cells in Tier 1 and Tier 2 share the same formula structure even though their cell addresses differ. `=F15+F16` and `=G15+G16` are the same structural pattern. Reviewing one representative is sufficient.

#### Normalisation
Convert every formula to a structural pattern by replacing cell addresses with abstract tokens:

```python
import re

def normalise_formula(formula: str, sheet: str) -> str:
    """
    =F15+F16          -> =COL+COL          (same-sheet same-column refs)
    =SUM(F15:F25)     -> =SUM(RANGE)
    =Sheet2!F15       -> =XSHEET!REF
    =F15*0.3          -> =REF*CONST
    """
    f = formula.upper()
    # Cross-sheet refs
    f = re.sub(r"'?[^'!\s]+'?![A-Z]+\d+", "XSHEET!REF", f)
    # Ranges
    f = re.sub(r"\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+", "RANGE", f)
    # Cell refs
    f = re.sub(r"\$?[A-Z]+\$?\d+", "REF", f)
    # Numeric constants
    f = re.sub(r"\b\d+(\.\d+)?\b", "CONST", f)
    return f
```

#### Deduplication within each tier

```python
def deduplicate_by_pattern(cells: list[dict]) -> list[dict]:
    """
    Groups cells by (sheet, symbol, normalised_formula).
    Returns one representative per group: the cell with highest risk_score.
    Stores all other group members in representative["pattern_instances"].
    """
    from collections import defaultdict
    groups = defaultdict(list)

    for cell in cells:
        pattern = normalise_formula(cell["formula"], cell["sheet"])
        key = (cell["symbol"], pattern)
        groups[key].append(cell)

    representatives = []
    for key, group in groups.items():
        # Pick highest risk_score as representative
        rep = max(group, key=lambda c: c["risk_score"])
        rep["pattern_instances"] = [c["cell"] for c in group if c["cell"] != rep["cell"]]
        rep["pattern_instance_count"] = len(group)
        representatives.append(rep)

    return representatives
```

**Scale impact:**
- 3,000 Tier 1 cells may reduce to ~300 unique patterns
- 7,000 Tier 2 cells may reduce to ~500 unique patterns
- LLM total input: ~800 formula patterns regardless of original UF count

The actual reduction ratio depends on model design — highly templated models (rolling forecasts, multi-entity consolidations) will deduplicate aggressively. Custom-built bespoke models will deduplicate less but are also less common at scale.

---

### Step 9: Context Enrichment

**File:** `enricher.py`

Run only on deduplicated representatives (Tier 1 + Tier 2). Do not enrich Tier 3 cells.

```python
def enrich_cell(cell: dict, structure_map: dict, wb_values) -> dict:
    sm  = structure_map[cell["sheet"]]
    ws  = wb_values[cell["sheet"]]
    row = cell["row"]
    col = cell["col"]

    # Label: label_col on same row
    label = get_cell_value(ws, sm["label_col"], row) or f"Row {row}"

    # Units: unit_col on same row
    units = get_cell_value(ws, sm.get("unit_col"), row) if sm.get("unit_col") else None

    # Period: timeline_row at same column
    period = None
    if sm.get("timeline_row"):
        period = get_cell_value_by_rowcol(ws, sm["timeline_row"], col)

    # Section: nearest section_header at or above this row
    section = "General"
    for sh in reversed(sm["section_headers"]):
        if sh["row"] <= row:
            section = sh["label"]
            break

    # Dependency labels and values
    dep_details = []
    for dep_sheet, dep_coord in cell.get("raw_dependencies", []):
        if dep_sheet not in structure_map:
            dep_details.append({"sheet": dep_sheet, "cell": dep_coord, "label": dep_coord, "value": None})
            continue
        dep_ws  = wb_values[dep_sheet]
        dep_sm  = structure_map[dep_sheet]
        dep_row = openpyxl.utils.cell.coordinate_to_tuple(dep_coord)[0]
        dep_lbl = get_cell_value(dep_ws, dep_sm["label_col"], dep_row) or dep_coord
        dep_val = dep_ws[dep_coord].value
        dep_details.append({"sheet": dep_sheet, "cell": dep_coord, "label": dep_lbl, "value": dep_val})

    return {
        **cell,
        "label":        label,
        "units":        units,
        "period":       period,
        "section":      section,
        "dependencies": dep_details
    }
```

---

### Step 10: Agentic LLM Review

**File:** `llm_reviewer.py`

#### Input scope
- Tier 1 deduplicated representatives (~300 patterns)
- Tier 2 deduplicated representatives (~500 patterns)
- Total: ~800 patterns maximum in practice, bounded regardless of UF count

#### Tier 1 vs Tier 2 prompt strategy

**Tier 1 — Full review prompt:**
Uses complete enriched context including dependency labels, values, section, period, units.
Max 20 cells per batch.

**Tier 2 — Lightweight review prompt:**
Sends formula + label + symbol only. No dependency detail.
Asks only: "Is there an obvious mathematical integrity issue with this formula given its label?"
Max 50 cells per batch.

This two-tier prompt strategy halves token cost on Tier 2 while still catching egregious errors.

#### System Prompt (Tier 1)
```
You are a financial model integrity reviewer at a Big 4 accounting firm.

You are reviewing UNIQUE formulas from a financial model. These cells have been
pre-selected as high-risk by a dependency graph analysis — they sit on the critical
path and errors here propagate to many downstream outputs.

Each cell includes: sheet, cell reference, symbol type (F=formula, S=sum, C=callup),
label, units, section, period, formula string, computed value, and full dependency
detail (label + value of each referenced cell).

YOUR ONLY JOB: identify MATHEMATICAL INTEGRITY issues.

Do NOT comment on:
- Naming or labelling conventions
- Whether a value should be a formula (handled separately)
- Formatting or style

Flag issues in these categories only:
INCORRECT_AGGREGATION  - formula sums/subtracts wrong cells for the stated label
SIGN_ERROR             - value should be negative but is positive or vice versa
MISSING_COMPONENT      - subtotal is missing a line item logically expected in section
WRONG_OPERATOR         - multiply where divide is correct or vice versa
UNIT_MISMATCH          - formula mixes cells with incompatible units
SCOPE_ERROR            - references wrong period, section, or sheet for stated label
CALLUP_MISMATCH        - C-type cell references source that does not match its label

Respond ONLY in this JSON format, no preamble:
{
  "issues": [
    {
      "sheet":        "P&L",
      "cell":         "F15",
      "label":        "Total Revenue",
      "symbol":       "F",
      "issue_type":   "MISSING_COMPONENT",
      "severity":     "CRITICAL",
      "description":  "...",
      "suggested_fix":"..."
    }
  ]
}

If no issues: { "issues": [] }
```

#### System Prompt (Tier 2)
```
You are a financial model integrity reviewer.

You will receive a batch of formula cells with label and formula only.
Flag ONLY obvious mathematical integrity issues — wrong operator, clear sign error,
or aggregation that is structurally wrong for the label.

Do not flag anything you are uncertain about. If the formula looks plausible given
the label, return no issue for that cell. Tier 2 is a fast pass — only flag
high-confidence issues.

Respond in the same JSON format. If uncertain: omit the cell entirely.
```

#### Cross-Section Consistency Pass (Final Agent Call)
After all tier reviews:
- Collect terminal output cells of each section (is_terminal=True)
- Send with prompt: "These are the final outputs of each model section. Do they flow correctly into each other? Check for sign flips, unit changes, or missing bridges between sections."
- Findings tagged `issue_type: CROSS_SECTION_INCONSISTENCY`

#### Agentic Loop
```python
async def run_review(
    enriched_tier1: list,
    enriched_tier2: list,
    structure_map: dict
) -> list:
    issues = []

    # Tier 1: full review, batch of 20
    t1_groups = group_by_sheet_and_section(enriched_tier1)
    for group_key, batch in t1_groups.items():
        for chunk in chunked(batch, 20):
            response = await call_claude(TIER1_SYSTEM_PROMPT, build_user_prompt(chunk))
            issues.extend(parse_json_response(response))

    # Tier 2: lightweight review, batch of 50
    for chunk in chunked(enriched_tier2, 50):
        response = await call_claude(TIER2_SYSTEM_PROMPT, build_lightweight_prompt(chunk))
        issues.extend(parse_json_response(response))

    # Cross-section pass
    terminal_cells = [c for c in enriched_tier1 if c.get("is_terminal")]
    if len(terminal_cells) > 1:
        response = await call_claude(CROSS_SECTION_PROMPT, build_cross_section_prompt(terminal_cells))
        issues.extend(parse_json_response(response))

    return issues
```

---

### Step 11: Result Propagation

**File:** `propagator.py`

When a finding is identified on a representative cell, propagate that finding to all cells sharing the same formula pattern (stored in `pattern_instances`).

```python
def propagate_findings(issues: list[dict], representatives: list[dict]) -> list[dict]:
    propagated = []
    for issue in issues:
        rep = find_representative(issue["cell"], issue["sheet"], representatives)
        if rep and rep.get("pattern_instances"):
            issue["instances"] = [issue["cell"]] + rep["pattern_instances"]
            issue["instance_count"] = len(issue["instances"])
        else:
            issue["instances"] = [issue["cell"]]
            issue["instance_count"] = 1
        propagated.append(issue)
    return propagated
```

This is important: a single LLM finding on one representative can flag 10–50 actual model cells if it is a systemic pattern error. The report must surface this clearly.

---

### Step 12: Report Generation

**File:** `report_generator.py`

#### JSON Report Structure
```json
{
  "job_id": "abc123",
  "model_filename": "ClientModel_v3.xlsx",
  "map_filename":   "ClientModel_v3_map.xlsx",
  "reviewed_at":    "2025-05-25T10:30:00Z",
  "summary": {
    "total_ufs":              20000,
    "symbol_breakdown":       { "F": 9800, "S": 4200, "C": 3000, "N": 2000, "X": 1000 },
    "tier_breakdown":         { "tier1": 2550, "tier2": 5950, "tier3": 8500, "auto": 3000 },
    "llm_calls_made":         87,
    "patterns_reviewed":      820,
    "total_issues":           34,
    "critical":               8,
    "warning":                16,
    "info":                   10,
    "cells_affected_by_issues": 210
  },
  "graph_analysis": {
    "circular_references":      [],
    "broken_references":        ["DCF!Z99"],
    "external_links_in_chain":  ["P&L!F22"],
    "hardcoded_mid_chain":      ["BS!D8", "BS!D9"]
  },
  "issues": [
    {
      "sheet":           "P&L",
      "cell":            "F15",
      "label":           "Total Revenue",
      "symbol":          "S",
      "tier":            1,
      "section":         "Revenue Build",
      "period":          "FY2025",
      "formula":         "=SUM(F12:F13)",
      "computed_value":  60,
      "issue_type":      "MISSING_COMPONENT",
      "severity":        "CRITICAL",
      "description":     "Total Revenue sums F12:F13 but F14 (Other Revenue=8) is in the same section and excluded.",
      "suggested_fix":   "Change to =SUM(F12:F14)",
      "instances":       ["F15", "G15", "H15", "I15", "J15"],
      "instance_count":  5
    }
  ]
}
```

#### HTML Report
- Standalone single-file HTML, no CDN
- Header: model name, reviewed date, summary stats
- Tier summary panel: what was reviewed at each tier level
- Issues table: sortable, filterable by tier/severity/symbol/sheet
- Instance expansion: click an issue to see all affected cells
- Graph analysis: collapsible section
- Print-ready, neutral styling

---

## 7. File & Folder Structure

```
/
├── frontend/
│   ├── app/
│   │   ├── page.tsx                        # Dual upload page
│   │   ├── results/[jobId]/page.tsx        # Results + download
│   │   └── api/
│   │       ├── review/route.ts
│   │       ├── status/[jobId]/route.ts
│   │       └── report/[jobId]/route.ts
│   ├── components/
│   │   ├── DualFileUpload.tsx
│   │   ├── IssuesTable.tsx
│   │   ├── SummaryCard.tsx
│   │   ├── TierBreakdown.tsx
│   │   └── ProgressIndicator.tsx
│   └── package.json
│
├── backend/
│   ├── main.py                   # FastAPI app, routes, background tasks
│   ├── map_parser.py             # Step 0
│   ├── parser.py                 # Step 1
│   ├── structure_detector.py     # Step 2
│   ├── dependency_graph.py       # Step 3
│   ├── risk_scorer.py            # Step 4
│   ├── tier_assigner.py          # Step 5
│   ├── auto_flagger.py           # Step 6
│   ├── tier3_checker.py          # Step 7
│   ├── deduplicator.py           # Step 8
│   ├── enricher.py               # Step 9
│   ├── llm_reviewer.py           # Step 10
│   ├── propagator.py             # Step 11
│   ├── report_generator.py       # Step 12
│   ├── job_store.py              # In-memory job state
│   └── requirements.txt
│
└── README.md
```

---

## 8. Environment Variables

```env
# Backend
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
MAX_FILE_SIZE_MB=50

# Tier thresholds (percentile-based — these are fallback overrides only)
TIER1_PERCENTILE=85
TIER2_PERCENTILE=50

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 9. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Map file has 0 symbols | Abort: "Map file appears empty or invalid" |
| Map sheet not in model | Warn in report, skip sheet |
| Model cell in whitelist is empty | Note as structural anomaly, skip |
| Structure detection fails | Fall back to raw cell coord as label, continue |
| All cells score identically (flat model) | Fall back to fixed percentile thresholds |
| Claude API timeout on a batch | Retry once, then mark batch as "unreviewed — API error" |
| Circular reference detected | Auto-flag CRITICAL, remove from LLM review |
| File >50MB | Reject at upload |
| Non-xlsx file | Reject at upload |
| Pattern dedup produces 0 representatives | Skip LLM for that tier, log warning |

---

## 10. Build Order for Claude Code

Strictly follow this sequence — each step depends on the previous:

1. `map_parser.py` + unit test with sample map file
2. `parser.py` + validate whitelist extraction against map
3. `structure_detector.py`
4. `dependency_graph.py` + verify node metrics (out_degree, descendants, is_terminal)
5. `risk_scorer.py` + spot check scores on sample cells
6. `tier_assigner.py` + verify percentile thresholds produce reasonable tier sizes
7. `auto_flagger.py` (N, X, graph errors)
8. `tier3_checker.py`
9. `deduplicator.py` + verify pattern normalisation on sample formulas
10. `enricher.py`
11. `llm_reviewer.py` + cross-section pass
12. `propagator.py`
13. `report_generator.py` (JSON + HTML)
14. `main.py` — wire full pipeline into FastAPI with background tasks + progress tracking
15. Frontend — dual upload, results page, API proxy routes
16. End-to-end integration test: small model (100 UFs) + large model (5,000+ UFs)

---

## 11. Success Criteria

- Correctly handles models from 100 to 20,000+ UFs without code changes
- LLM call count stays bounded regardless of UF count (target: <150 calls for any model)
- Tier assignment produces meaningful distribution — Tier 1 never exceeds 20% of total UFs
- Pattern deduplication reduces Tier 1+2 cell count by at least 60% before LLM review
- Auto-flagging covers all N and X cells with zero LLM calls
- Full pipeline completes in under 5 minutes for a 20,000 UF model
- Instance propagation correctly attributes pattern findings to all affected cells
- Report downloads as valid JSON and standalone HTML
- No crashes on any well-formed model + map file pair
