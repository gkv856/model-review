"""
Step 12 — Report Generator
Input:  all pipeline outputs
Output: JSON report dict + standalone HTML string (no CDN dependencies)
"""

import json
from collections import Counter
from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)

_SEV_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def _sort_issues(issues: list[dict]) -> list[dict]:
    return sorted(issues, key=lambda i: (_SEV_ORDER.get(i.get("severity", "INFO"), 99), i.get("tier", 99)))


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
    """
    Input:  all pipeline data
    Output: structured JSON report dict per PRD §Step 12
    """
    all_issues = _sort_issues(issues + auto_issues)

    sym_counts  = Counter(c["symbol"] for c in cells)
    tier_counts: dict[str, int] = {"tier1": 0, "tier2": 0, "tier3": 0, "auto": 0}
    for c in cells:
        t = c.get("tier")
        if t == 1:
            tier_counts["tier1"] += 1
        elif t == 2:
            tier_counts["tier2"] += 1
        elif t == 3:
            tier_counts["tier3"] += 1
        elif t == "AUTO":
            tier_counts["auto"] += 1

    sev_counts    = Counter(i.get("severity", "INFO") for i in all_issues)
    cells_affected = len({(i.get("sheet"), i.get("cell")) for i in all_issues})

    circular   = [f"{i['sheet']}!{i['cell']}" for i in auto_issues if i.get("issue_type") == "circular_ref"]
    broken     = [f"{i['sheet']}!{i['cell']}" for i in auto_issues if i.get("issue_type") == "broken_ref"]
    x_in_chain = [f"{i['sheet']}!{i['cell']}" for i in auto_issues if i.get("issue_type") == "x_in_chain"]
    hw_mid     = [f"{i['sheet']}!{i['cell']}" for i in issues     if i.get("issue_type") == "hardcoded_mid_chain"]

    report = {
        "job_id":         job_id,
        "model_filename": model_filename,
        "map_filename":   map_filename,
        "reviewed_at":    datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_ufs":                len(cells),
            "symbol_breakdown":         dict(sym_counts),
            "tier_breakdown":           tier_counts,
            "llm_calls_made":           llm_calls_made,
            "patterns_reviewed":        patterns_reviewed,
            "total_issues":             len(all_issues),
            "critical":                 sev_counts.get("CRITICAL", 0),
            "warning":                  sev_counts.get("WARNING", 0),
            "info":                     sev_counts.get("INFO", 0),
            "cells_affected_by_issues": cells_affected,
        },
        "graph_analysis": {
            "circular_references":     circular,
            "broken_references":       broken,
            "external_links_in_chain": x_in_chain,
            "hardcoded_mid_chain":     hw_mid,
        },
        "issues": all_issues,
    }
    logger.info(
        "[report_generator] Report built: %d issues, %d cells affected",
        len(all_issues), cells_affected,
    )
    return report


# ── HTML report ───────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Model Review — {model_filename}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;font-size:14px;line-height:1.5}}
.container{{max-width:1200px;margin:0 auto;padding:24px}}
h1{{font-size:20px;font-weight:700;color:#f8fafc;margin-bottom:4px}}
.meta{{color:#64748b;font-size:12px;margin-bottom:24px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px}}
.card{{background:#1e2435;border:1px solid #2d3748;border-radius:8px;padding:16px}}
.card-label{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:4px}}
.card-value{{font-size:24px;font-weight:700;color:#f8fafc}}
.critical{{color:#f87171}}.warning{{color:#fbbf24}}.info{{color:#60a5fa}}
.tier1{{color:#f87171}}.tier2{{color:#fbbf24}}.tier3{{color:#34d399}}
section{{margin-bottom:24px}}
section h2{{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid #2d3748}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
select{{background:#1e2435;border:1px solid #2d3748;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:12px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#64748b;padding:8px 10px;border-bottom:1px solid #2d3748;white-space:nowrap}}
td{{padding:8px 10px;border-bottom:1px solid #1a2030;vertical-align:top;font-size:12px}}
tr:hover td{{background:#1a2030}}
.badge{{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-critical{{background:#450a0a;color:#f87171;border:1px solid #7f1d1d}}
.badge-warning{{background:#451a03;color:#fbbf24;border:1px solid #78350f}}
.badge-info{{background:#0c1a35;color:#60a5fa;border:1px solid #1e3a5f}}
.badge-tier1{{background:#450a0a;color:#f87171}}.badge-tier2{{background:#451a03;color:#fbbf24}}
.badge-tier3{{background:#0c2a1a;color:#34d399}}.badge-auto{{background:#1e2435;color:#94a3b8}}
.mono{{font-family:'Fira Code',monospace;font-size:11px;background:#0f1117;padding:1px 5px;border-radius:3px;color:#c084fc}}
.instances{{font-size:11px;color:#64748b;margin-top:4px;cursor:pointer}}
.instances-list{{display:none;margin-top:4px;padding:6px;background:#0f1117;border-radius:4px}}
.instances-list.open{{display:block}}
.graph-flags{{display:flex;flex-wrap:wrap;gap:6px}}
.flag-chip{{font-family:monospace;font-size:11px;background:#1e2435;border:1px solid #2d3748;padding:2px 8px;border-radius:4px;color:#94a3b8}}
.hidden{{display:none}}
@media print{{body{{background:#fff;color:#000}}.card{{background:#f8f8f8;border-color:#e0e0e0}}table th,table td{{border-color:#e0e0e0}}}}
</style>
</head>
<body>
<div class="container">
<h1>{model_filename}</h1>
<p class="meta">Map: {map_filename} &nbsp;|&nbsp; Reviewed: {reviewed_at} &nbsp;|&nbsp; Job: {job_id}</p>

<div class="cards">
  <div class="card"><div class="card-label">Total UFs</div><div class="card-value">{total_ufs}</div></div>
  <div class="card"><div class="card-label">Total Issues</div><div class="card-value">{total_issues}</div></div>
  <div class="card"><div class="card-label">Critical</div><div class="card-value critical">{critical}</div></div>
  <div class="card"><div class="card-label">Warning</div><div class="card-value warning">{warning}</div></div>
  <div class="card"><div class="card-label">Info</div><div class="card-value info">{info}</div></div>
  <div class="card"><div class="card-label">LLM Calls</div><div class="card-value">{llm_calls_made}</div></div>
  <div class="card"><div class="card-label">Patterns</div><div class="card-value">{patterns_reviewed}</div></div>
  <div class="card"><div class="card-label">Cells Affected</div><div class="card-value">{cells_affected}</div></div>
</div>

<section>
<h2>Tier Breakdown</h2>
<div class="cards">
  <div class="card"><div class="card-label">Tier 1 (Critical Path)</div><div class="card-value tier1">{tier1}</div></div>
  <div class="card"><div class="card-label">Tier 2 (Standard)</div><div class="card-value tier2">{tier2}</div></div>
  <div class="card"><div class="card-label">Tier 3 (Rule-Based)</div><div class="card-value tier3">{tier3}</div></div>
  <div class="card"><div class="card-label">Auto-Flagged</div><div class="card-value">{auto}</div></div>
</div>
</section>

{graph_section}

<section>
<h2>Issues ({total_issues})</h2>
<div class="filters">
  <select id="f-tier" onchange="applyFilters()">
    <option value="">All Tiers</option>
    <option value="1">Tier 1</option>
    <option value="2">Tier 2</option>
    <option value="3">Tier 3</option>
    <option value="AUTO">Auto</option>
  </select>
  <select id="f-sev" onchange="applyFilters()">
    <option value="">All Severities</option>
    <option value="CRITICAL">Critical</option>
    <option value="WARNING">Warning</option>
    <option value="INFO">Info</option>
  </select>
  <select id="f-sym" onchange="applyFilters()">
    <option value="">All Symbols</option>
    <option value="F">F</option>
    <option value="S">S</option>
    <option value="C">C</option>
    <option value="N">N</option>
    <option value="X">X</option>
  </select>
  <select id="f-sheet" onchange="applyFilters()">
    <option value="">All Sheets</option>
    {sheet_options}
  </select>
</div>
<table id="issues-table">
<thead><tr>
  <th>Sheet</th><th>Cell</th><th>Label</th><th>Symbol</th>
  <th>Tier</th><th>Severity</th><th>Issue Type</th><th>Description</th>
  <th>Suggested Fix</th><th>Instances</th>
</tr></thead>
<tbody>
{issue_rows}
</tbody>
</table>
</section>
</div>
<script>
function applyFilters(){{
  const tier=document.getElementById('f-tier').value;
  const sev=document.getElementById('f-sev').value;
  const sym=document.getElementById('f-sym').value;
  const sheet=document.getElementById('f-sheet').value;
  document.querySelectorAll('#issues-table tbody tr').forEach(function(row){{
    const match=(
      (!tier||row.dataset.tier===tier)&&
      (!sev||row.dataset.sev===sev)&&
      (!sym||row.dataset.sym===sym)&&
      (!sheet||row.dataset.sheet===sheet)
    );
    row.classList.toggle('hidden',!match);
  }});
}}
function toggleInstances(el){{
  const list=el.nextElementSibling;
  list.classList.toggle('open');
}}
</script>
</body>
</html>"""

_GRAPH_SECTION_TEMPLATE = """<section>
<h2>Graph Analysis Flags</h2>
{content}
</section>"""


def _badge(text: str, cls: str) -> str:
    return f'<span class="badge badge-{cls}">{text}</span>'


def _sev_badge(sev: str) -> str:
    return _badge(sev, sev.lower())


def _tier_badge(tier) -> str:
    cls = f"tier{tier}".lower() if str(tier).isdigit() else "auto"
    return _badge(str(tier), cls)


def _issue_row(issue: dict) -> str:
    sev   = issue.get("severity", "INFO")
    tier  = issue.get("tier", "")
    sym   = issue.get("symbol", "")
    sheet = issue.get("sheet", "")
    cell  = issue.get("cell", "")

    instances = issue.get("instances", [])
    count     = issue.get("instance_count", 1)
    inst_html = ""
    if count > 1:
        inst_items = "".join(
            f"<div>{i[0]}!{i[1]}" if isinstance(i, (list, tuple)) else f"<div>{i}</div>"
            for i in instances
        )
        inst_html = (
            f'<div class="instances" onclick="toggleInstances(this)">'
            f'▶ {count} cells</div>'
            f'<div class="instances-list">{inst_items}</div>'
        )
    else:
        inst_html = '<div style="color:#64748b">1 cell</div>'

    formula_html = ""
    if issue.get("formula"):
        formula_html = f'<br><span class="mono">{issue["formula"][:80]}</span>'

    return (
        f'<tr data-tier="{tier}" data-sev="{sev}" data-sym="{sym}" data-sheet="{sheet}">'
        f'<td>{sheet}</td>'
        f'<td><span class="mono">{cell}</span></td>'
        f'<td>{issue.get("label","")}{formula_html}</td>'
        f'<td>{_badge(sym,"tier1") if sym else ""}</td>'
        f'<td>{_tier_badge(tier)}</td>'
        f'<td>{_sev_badge(sev)}</td>'
        f'<td><span style="font-family:monospace;font-size:11px">{issue.get("issue_type","")}</span></td>'
        f'<td>{issue.get("description","")}</td>'
        f'<td>{issue.get("suggested_fix","")}</td>'
        f'<td>{inst_html}</td>'
        f'</tr>'
    )


def build_html_report(report: dict) -> str:
    """
    Input:  JSON report dict from build_json_report
    Output: standalone single-file HTML string (no CDN)
    """
    s      = report["summary"]
    ga     = report["graph_analysis"]
    issues = report["issues"]

    graph_content_parts = []
    if ga["circular_references"]:
        chips = "".join(f'<span class="flag-chip">{r}</span>' for r in ga["circular_references"])
        graph_content_parts.append(f'<p style="color:#f87171;margin-bottom:6px">Circular References</p><div class="graph-flags">{chips}</div>')
    if ga["broken_references"]:
        chips = "".join(f'<span class="flag-chip">{r}</span>' for r in ga["broken_references"])
        graph_content_parts.append(f'<p style="color:#fbbf24;margin-bottom:6px;margin-top:12px">Broken References</p><div class="graph-flags">{chips}</div>')
    if ga["external_links_in_chain"]:
        chips = "".join(f'<span class="flag-chip">{r}</span>' for r in ga["external_links_in_chain"])
        graph_content_parts.append(f'<p style="color:#fbbf24;margin-bottom:6px;margin-top:12px">External Links in Chain</p><div class="graph-flags">{chips}</div>')

    graph_section = ""
    if graph_content_parts:
        graph_section = _GRAPH_SECTION_TEMPLATE.format(content="\n".join(graph_content_parts))

    sheets = sorted({i.get("sheet", "") for i in issues if i.get("sheet")})
    sheet_options = "\n".join(f'<option value="{sh}">{sh}</option>' for sh in sheets)

    issue_rows = "\n".join(_issue_row(i) for i in issues)

    tb = s["tier_breakdown"]
    html = _HTML_TEMPLATE.format(
        model_filename=report["model_filename"],
        map_filename=report["map_filename"],
        reviewed_at=report["reviewed_at"],
        job_id=report["job_id"],
        total_ufs=s["total_ufs"],
        total_issues=s["total_issues"],
        critical=s["critical"],
        warning=s["warning"],
        info=s["info"],
        llm_calls_made=s["llm_calls_made"],
        patterns_reviewed=s["patterns_reviewed"],
        cells_affected=s["cells_affected_by_issues"],
        tier1=tb.get("tier1", 0),
        tier2=tb.get("tier2", 0),
        tier3=tb.get("tier3", 0),
        auto=tb.get("auto", 0),
        graph_section=graph_section,
        sheet_options=sheet_options,
        issue_rows=issue_rows,
    )
    return html
