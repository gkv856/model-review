// Pipeline step definitions, CSV/JSON parsing, and per-step aggregation.

export type StepStatus = "pending" | "loading" | "ready" | "failed"
export type FileType = "csv" | "json"

export interface IPipelineStep {
  id: string
  filename: string
  name: string
  description: string
  explanation: string  // 1–2 sentences shown in the pipeline inspector
  fileType: FileType
}

export interface IStepStat {
  label: string
  value: string | number
}

export interface IStepData {
  status: StepStatus
  headers: string[]
  rows: Record<string, string>[]
  stats: IStepStat[]
  sizeBytes: number
  error?: string
}

// ── Step definitions ──────────────────────────────────────────────────────────

export const PIPELINE_STEPS: IPipelineStep[] = [
  {
    id: "01", filename: "01_map_parsed.csv", fileType: "csv",
    name: "Map Parsed", description: "Symbol whitelist from map file",
    explanation: "The VBA map file is read to build a whitelist of every named cell and its symbol — F (formula), S (sum), C (callup), N (hardcoded), or X (external link). Cells with no symbol are drag-copies and are discarded entirely; they never enter the pipeline.",
  },
  {
    id: "02", filename: "02_cells_parsed.csv", fileType: "csv",
    name: "Cells Parsed", description: "Model cells extracted",
    explanation: "Every cell in the model workbook is extracted: its formula or literal value, the sheet it lives on, its row/column position, and whether it carries a unique formula. This is the complete raw dataset that all downstream steps operate on.",
  },
  {
    id: "03", filename: "03_structure_map.json", fileType: "json",
    name: "Structure Detected", description: "Sheet layout & timeline analysis",
    explanation: "Each sheet's layout is reverse-engineered to find the timeline row, label column, unit column, and section headers. This structural map is what allows the enrichment step to attach human-readable context — period, label, section — to raw cell coordinates.",
  },
  {
    id: "04", filename: "04_graph_metrics.csv", fileType: "csv",
    name: "Dependency Graph", description: "Node metrics for all cells",
    explanation: "A directed graph is built from formula references: if A1 depends on B1, the edge runs B1→A1. Per-node metrics — descendants, ancestors, cross-sheet depth, terminal status — are computed here and feed directly into the risk scoring formula.",
  },
  {
    id: "05", filename: "05_cells_scored.csv", fileType: "csv",
    name: "Risk Scoring", description: "0–100 risk score per cell",
    explanation: "Each cell receives a 0–100 risk score combining six weighted components: depth in the dependency chain, whether it is a terminal output cell, cross-sheet complexity, symbol weight (F/S/C/N), ancestor breadth, and graph bridge status. Higher score means higher review priority.",
  },
  {
    id: "06", filename: "06_cells_tiered.csv", fileType: "csv",
    name: "Tier Assignment", description: "Percentile-based tier buckets",
    explanation: "Cells are ranked by risk score and bucketed using percentile thresholds: the top 15% become Tier 1 (full LLM review), the next 35% Tier 2 (lightweight review), and the rest Tier 3 (rule checks only). Hardcoded (N) and external-link (X) cells are auto-assigned and bypass this ranking.",
  },
  {
    id: "07", filename: "07_auto_flags.csv", fileType: "csv",
    name: "Auto Flagged", description: "N/X cells and graph errors",
    explanation: "Three rule-based detectors fire without any LLM: external links buried inside formula dependency chains (X-in-chain), circular references detected via graph cycle analysis, and formula references pointing to cells that don't exist in the workbook.",
  },
  {
    id: "08", filename: "08_tier3_issues.csv", fileType: "csv",
    name: "Tier 3 Checks", description: "Rule-based deterministic checks",
    explanation: "Five deterministic rules run on Tier 3 cells only: divide-by-zero risk (formula contains '/' and a predecessor is zero), hardcoded values mid-chain, self-references, empty sum ranges, and mismatched units between a cell and its direct predecessors.",
  },
  {
    id: "09", filename: "09_deduplication.csv", fileType: "csv",
    name: "Deduplication", description: "Identical formula patterns collapsed",
    explanation: "Cells whose formulas share the same structural pattern (same operations, same relative reference layout) are collapsed into one representative. This is what bounds LLM cost regardless of model size — a workbook with 8,000 cells may reduce to 300 unique patterns sent for review.",
  },
  {
    id: "10", filename: "10_cells_enriched.csv", fileType: "csv",
    name: "Enrichment", description: "Label, units, period, section added",
    explanation: "Each deduplicated representative is annotated with its human-readable label (from the label column), units, time period (from the timeline row), section heading, and the values of its direct predecessor cells. This is the full context the LLM reads — without it, a formula like '=B5/C5' is meaningless.",
  },
  {
    id: "11", filename: "11_llm_issues.csv", fileType: "csv",
    name: "LLM Review", description: "AI model findings",
    explanation: "The AI model reviews enriched representatives in three passes: Tier 1 cells in detail (batches of 20, grouped by sheet and section), Tier 2 lightly (batches of 50, formula and label only), and all terminal output cells together to detect cross-section sign flips and missing linkages.",
  },
  {
    id: "12", filename: "12_propagated_issues.csv", fileType: "csv",
    name: "Final Issues", description: "Propagated to all pattern instances",
    explanation: "Every finding is propagated from its representative cell back to all cells that share the same formula pattern. An issue flagged on one cell can affect dozens of instances across the model; the instance_count column shows the total model-wide impact of each finding.",
  },
]

// ── CSV parser ────────────────────────────────────────────────────────────────

export function parseCSV(text: string): { headers: string[]; rows: Record<string, string>[] } {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length === 0) return { headers: [], rows: [] }

  const parseRow = (line: string): string[] => {
    const values: string[] = []
    let current = ""
    let inQuotes = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (ch === '"') {
        inQuotes = !inQuotes
      } else if (ch === "," && !inQuotes) {
        values.push(current.trim())
        current = ""
      } else {
        current += ch
      }
    }
    values.push(current.trim())
    return values
  }

  const headers = parseRow(lines[0])
  const rows = lines.slice(1).filter(Boolean).map((line) => {
    const vals = parseRow(line)
    return Object.fromEntries(headers.map((h, i) => [h, vals[i] ?? ""]))
  })
  return { headers, rows }
}

// ── JSON → flat rows ──────────────────────────────────────────────────────────

export function parseStructureJSON(text: string): { headers: string[]; rows: Record<string, string>[] } {
  try {
    const data = JSON.parse(text) as Record<string, Record<string, unknown>>
    const headers = ["sheet", "timeline_row", "label_col", "unit_col", "data_start_col", "sections"]
    const rows = Object.entries(data).map(([sheet, sm]) => ({
      sheet,
      timeline_row: String(sm.timeline_row ?? ""),
      label_col:    String(sm.label_col ?? ""),
      unit_col:     String(sm.unit_col ?? ""),
      data_start_col: String(sm.data_start_col ?? ""),
      sections:     String((sm.section_headers as unknown[])?.length ?? 0),
    }))
    return { headers, rows }
  } catch {
    return { headers: [], rows: [] }
  }
}

// ── Per-step aggregation ──────────────────────────────────────────────────────

function countBy(rows: Record<string, string>[], key: string): Record<string, number> {
  return rows.reduce<Record<string, number>>((acc, r) => {
    const v = r[key] ?? "?"
    acc[v] = (acc[v] ?? 0) + 1
    return acc
  }, {})
}

function numStats(rows: Record<string, string>[], key: string): { min: number; max: number; avg: number } {
  const vals = rows.map((r) => parseFloat(r[key] ?? "0")).filter((v) => !isNaN(v))
  if (!vals.length) return { min: 0, max: 0, avg: 0 }
  const sum = vals.reduce((a, b) => a + b, 0)
  return { min: Math.min(...vals), max: Math.max(...vals), avg: sum / vals.length }
}

export function aggregateStep(step: IPipelineStep, rows: Record<string, string>[], rawText: string): IStepStat[] {
  switch (step.id) {
    case "01": {
      const bySymbol = countBy(rows, "symbol")
      const sheets = new Set(rows.map((r) => r.sheet)).size
      return [
        { label: "Total cells", value: rows.length },
        { label: "Sheets", value: sheets },
        ...Object.entries(bySymbol).sort().map(([sym, n]) => ({ label: sym, value: n })),
      ]
    }
    case "02": {
      const sheets = new Set(rows.map((r) => r.sheet)).size
      const formulas = rows.filter((r) => r.is_formula === "True").length
      const bySymbol = countBy(rows, "symbol")
      return [
        { label: "Total cells", value: rows.length },
        { label: "Sheets", value: sheets },
        { label: "Formulas", value: formulas },
        ...Object.entries(bySymbol).sort().map(([sym, n]) => ({ label: sym, value: n })),
      ]
    }
    case "03": {
      try {
        const data = JSON.parse(rawText) as Record<string, Record<string, unknown>>
        const sheets = Object.keys(data).length
        const withTimeline = Object.values(data).filter((s) => s.timeline_row != null).length
        const withLabel = Object.values(data).filter((s) => s.label_col != null).length
        const totalSections = Object.values(data).reduce((sum, s) => {
          const headers = s.section_headers as unknown[]
          return sum + (Array.isArray(headers) ? headers.length : 0)
        }, 0)
        return [
          { label: "Sheets", value: sheets },
          { label: "With timeline", value: withTimeline },
          { label: "With labels", value: withLabel },
          { label: "Sections", value: totalSections },
        ]
      } catch {
        return [{ label: "Rows", value: rows.length }]
      }
    }
    case "04": {
      const terminals = rows.filter((r) => r.is_terminal === "True").length
      const crossSheet = rows.filter((r) => parseFloat(r.sheet_depth ?? "0") > 0).length
      const descStats = numStats(rows, "descendants")
      return [
        { label: "Total nodes", value: rows.length },
        { label: "Terminal", value: terminals },
        { label: "Cross-sheet", value: crossSheet },
        { label: "Max descendants", value: descStats.max },
      ]
    }
    case "05": {
      const { min, max, avg } = numStats(rows, "risk_score")
      const high = rows.filter((r) => parseFloat(r.risk_score ?? "0") >= 60).length
      const med  = rows.filter((r) => { const s = parseFloat(r.risk_score ?? "0"); return s >= 30 && s < 60 }).length
      const low  = rows.filter((r) => parseFloat(r.risk_score ?? "0") < 30).length
      return [
        { label: "Scored cells", value: rows.length },
        { label: "Min", value: min.toFixed(1) },
        { label: "Max", value: max.toFixed(1) },
        { label: "Avg", value: avg.toFixed(1) },
        { label: "High (≥60)", value: high },
        { label: "Med (30–60)", value: med },
        { label: "Low (<30)", value: low },
      ]
    }
    case "06": {
      const byTier = countBy(rows, "tier")
      return [
        { label: "Total cells", value: rows.length },
        { label: "Tier 1", value: byTier["1"] ?? 0 },
        { label: "Tier 2", value: byTier["2"] ?? 0 },
        { label: "Tier 3", value: byTier["3"] ?? 0 },
        { label: "Auto", value: byTier["AUTO"] ?? 0 },
      ]
    }
    case "07":
    case "08": {
      const bySev  = countBy(rows, "severity")
      const byType = countBy(rows, "issue_type")
      const topTypes = Object.entries(byType).sort((a, b) => b[1] - a[1]).slice(0, 3)
      return [
        { label: "Total issues", value: rows.length },
        { label: "Critical", value: bySev["CRITICAL"] ?? 0 },
        { label: "Warning",  value: bySev["WARNING"]  ?? 0 },
        { label: "Info",     value: bySev["INFO"]     ?? 0 },
        ...topTypes.map(([type, n]) => ({ label: type.replace(/_/g, " "), value: n })),
      ]
    }
    case "09": {
      const totalInstances = rows.reduce((sum, r) => sum + (parseInt(r.pattern_instance_count ?? "1")), 0)
      const reduction = totalInstances > 0 ? Math.round((1 - rows.length / totalInstances) * 100) : 0
      const byTier = countBy(rows, "tier")
      return [
        { label: "Patterns", value: rows.length },
        { label: "Total cells", value: totalInstances },
        { label: "Reduction", value: `${reduction}%` },
        { label: "Tier 1 reps", value: byTier["1"] ?? 0 },
        { label: "Tier 2 reps", value: byTier["2"] ?? 0 },
      ]
    }
    case "10": {
      const withUnits   = rows.filter((r) => r.units && r.units !== "None").length
      const withPeriod  = rows.filter((r) => r.period && r.period !== "None").length
      const sections    = new Set(rows.map((r) => r.section).filter(Boolean)).size
      return [
        { label: "Enriched cells", value: rows.length },
        { label: "With units",     value: withUnits },
        { label: "With period",    value: withPeriod },
        { label: "Unique sections", value: sections },
      ]
    }
    case "11":
    case "12": {
      const bySev  = countBy(rows, "severity")
      const byTier = countBy(rows, "tier")
      const stats: IStepStat[] = [
        { label: "Total issues", value: rows.length },
        { label: "Critical", value: bySev["CRITICAL"] ?? 0 },
        { label: "Warning",  value: bySev["WARNING"]  ?? 0 },
        { label: "Info",     value: bySev["INFO"]     ?? 0 },
      ]
      if (step.id === "12") {
        const totalAffected = rows.reduce((sum, r) => sum + (parseInt(r.instance_count ?? "1")), 0)
        stats.push({ label: "Cells affected", value: totalAffected })
      }
      if (byTier["1"]) stats.push({ label: "Tier 1", value: byTier["1"] })
      if (byTier["2"]) stats.push({ label: "Tier 2", value: byTier["2"] })
      return stats
    }
    default:
      return [{ label: "Rows", value: rows.length }]
  }
}
