"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  ArrowLeft, CheckCircle2, Clock, Loader2, X,
  BarChart2, History, ChevronRight, Info, ChevronDown, Layers,
  AlertCircle, Minus,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { useJobStatus } from "@/hooks/useJobStatus"
import { usePipelineData } from "@/hooks/usePipelineData"
import { PIPELINE_STEPS, IStepData, IPipelineStep } from "@/lib/pipelineSteps"
import { cn } from "@/lib/utils"

interface IPageProps {
  params: Promise<{ jobId: string }>
}

interface IPastRun {
  job_id: string
  file_count: number
  model_filename: string | null
  started_at: string | null
}

interface IPromptRecord {
  pass: "tier1" | "tier2" | "cross_section"
  batch: number
  cell_count: number
  cell_refs: string[]
  system_prompt: string
  user_prompt: string
  raw_response?: string
}

// ── Executive Summary panel ───────────────────────────────────────────────────

interface ISummaryPanelProps {
  stepData: Record<string, IStepData>
  modelName: string | null
}

function MetricCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className="rounded-lg bg-white/[0.04] border border-white/[0.06] px-4 py-3.5 flex flex-col gap-1">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={cn("text-2xl font-bold tabular-nums leading-none", accent ?? "text-foreground")}>{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground leading-none">{sub}</p>}
    </div>
  )
}

function SummaryPanel({ stepData, modelName }: ISummaryPanelProps) {
  const s = (id: string) => stepData[id]
  const ready = (id: string) => s(id)?.status === "ready"

  // Tier breakdown
  const tierRows  = ready("06") ? s("06").rows : []
  const t1 = tierRows.filter(r => r.tier === "1").length
  const t2 = tierRows.filter(r => r.tier === "2").length
  const t3 = tierRows.filter(r => r.tier === "3").length
  const auto = tierRows.filter(r => r.tier === "AUTO").length
  const totalCells = tierRows.length

  // Issues
  const issueRows  = ready("12") ? s("12").rows : []
  const critical   = issueRows.filter(r => r.severity === "CRITICAL").length
  const warning    = issueRows.filter(r => r.severity === "WARNING").length
  const info       = issueRows.filter(r => r.severity === "INFO").length
  const totalIssues = issueRows.length

  // Sources
  const llmIssues  = ready("11") ? s("11").rows.length : 0
  const autoIssues = ready("07") ? s("07").rows.length : 0
  const ruleIssues = ready("08") ? s("08").rows.length : 0

  // Dedup stats
  const dedupRows = ready("09") ? s("09").rows : []
  const patterns  = dedupRows.length
  const instances = dedupRows.reduce((n, r) => n + parseInt(r.pattern_instance_count || "1"), 0)
  const reduction = instances > 0 ? Math.round((1 - patterns / instances) * 100) : 0

  // Sheets
  const sheets = ready("01") ? new Set(s("01").rows.map(r => r.sheet)).size : 0

  const isComplete = ready("12")
  const readySteps = PIPELINE_STEPS.filter(st => s(st.id)?.status === "ready").length

  return (
    <div className="rounded-xl border border-white/10 bg-[#13161f] flex flex-col h-full overflow-y-auto shadow-xl shadow-black/40">
      {/* Header */}
      <div className="px-6 py-5 border-b border-white/[0.06] shrink-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center">
                <Layers className="w-3.5 h-3.5 text-white/60" />
              </div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Executive Summary
              </p>
            </div>
            <h2 className="text-lg font-bold text-foreground mt-1">
              {modelName ?? "Model Review"}
            </h2>
          </div>
          <div className="text-right shrink-0">
            <p className={cn("text-xs font-semibold", isComplete ? "text-emerald-400" : "text-amber-400")}>
              {isComplete ? "All stages ready" : `${readySteps} / ${PIPELINE_STEPS.length} stages`}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{totalCells} cells analysed</p>
          </div>
        </div>
      </div>

      <div className="px-6 py-5 flex flex-col gap-6">
        {/* Top metrics row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard label="Total cells" value={totalCells.toLocaleString()} sub={`${sheets} sheets`} />
          <MetricCard label="Total issues" value={totalIssues} sub={isComplete ? "propagated" : "so far"} />
          <MetricCard label="Patterns sent to LLM" value={patterns} sub={`${reduction}% dedup reduction`} />
          <MetricCard
            label="Critical issues"
            value={critical}
            sub={critical > 0 ? "require attention" : "none found"}
            accent={critical > 0 ? "text-red-400" : "text-emerald-400"}
          />
        </div>

        {/* Tier distribution */}
        {totalCells > 0 && (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2.5">
              Tier Distribution
            </p>
            <div className="flex h-2 rounded-full overflow-hidden gap-px bg-white/5 mb-2">
              {t1 > 0 && <div className="bg-red-500/70"    style={{ width: `${(t1   / totalCells) * 100}%` }} />}
              {t2 > 0 && <div className="bg-amber-500/70"  style={{ width: `${(t2   / totalCells) * 100}%` }} />}
              {t3 > 0 && <div className="bg-emerald-500/50" style={{ width: `${(t3  / totalCells) * 100}%` }} />}
              {auto > 0 && <div className="bg-white/20"    style={{ width: `${(auto / totalCells) * 100}%` }} />}
            </div>
            <div className="flex gap-4 flex-wrap">
              {[
                { label: "Tier 1 — full LLM", n: t1,   color: "bg-red-500/70",    text: "text-red-400" },
                { label: "Tier 2 — light LLM", n: t2,  color: "bg-amber-500/70",  text: "text-amber-400" },
                { label: "Tier 3 — rules only", n: t3, color: "bg-emerald-500/50", text: "text-emerald-400" },
                { label: "Auto (N/X)",  n: auto,        color: "bg-white/20",      text: "text-muted-foreground" },
              ].map(({ label, n, color, text }) => (
                <div key={label} className="flex items-center gap-1.5">
                  <div className={cn("w-2 h-2 rounded-full shrink-0", color)} />
                  <span className={cn("text-xs font-semibold tabular-nums", text)}>{n}</span>
                  <span className="text-[11px] text-muted-foreground">{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Issue breakdown */}
        {totalIssues > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* By severity */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2.5">
                Issues by Severity
              </p>
              <div className="flex flex-col gap-1.5">
                {[
                  { label: "Critical", n: critical, bg: "bg-red-500/20",     text: "text-red-400",     bar: "bg-red-500/60" },
                  { label: "Warning",  n: warning,  bg: "bg-amber-500/20",   text: "text-amber-400",   bar: "bg-amber-500/60" },
                  { label: "Info",     n: info,     bg: "bg-blue-500/20",    text: "text-blue-400",    bar: "bg-blue-500/60" },
                ].map(({ label, n, bg, text, bar }) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className={cn("text-[10px] font-semibold w-14 px-1.5 py-0.5 rounded text-center", bg, text)}>
                      {label}
                    </span>
                    <div className="flex-1 h-1.5 rounded-full bg-white/5">
                      <div className={cn("h-full rounded-full", bar)}
                           style={{ width: totalIssues > 0 ? `${(n / totalIssues) * 100}%` : "0" }} />
                    </div>
                    <span className={cn("text-xs font-bold tabular-nums w-6 text-right", text)}>{n}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* By source */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2.5">
                Issues by Source
              </p>
              <div className="flex flex-col gap-1.5">
                {[
                  { label: "LLM Review",    n: llmIssues,  bar: "bg-orange-500/60" },
                  { label: "Auto Flagged",  n: autoIssues, bar: "bg-red-500/60" },
                  { label: "Rule Checks",   n: ruleIssues, bar: "bg-red-400/50" },
                ].map(({ label, n, bar }) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground w-24 truncate">{label}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-white/5">
                      <div className={cn("h-full rounded-full", bar)}
                           style={{ width: totalIssues > 0 ? `${(n / totalIssues) * 100}%` : "0" }} />
                    </div>
                    <span className="text-xs font-bold tabular-nums text-foreground/80 w-6 text-right">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {!isComplete && (
          <p className="text-xs text-muted-foreground/50 text-center py-4">
            Summary updates as stages complete
          </p>
        )}
      </div>
    </div>
  )
}

// ── LLM Prompts section (shown inside step 11 detail) ────────────────────────

function PromptsSection({ prompts }: { prompts: IPromptRecord[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null)

  const passLabel = (p: IPromptRecord["pass"]) =>
    p === "tier1" ? "Tier 1 — Full Review" :
    p === "tier2" ? "Tier 2 — Lightweight" :
    "Cross-Section"

  const passColor = (p: IPromptRecord["pass"]) =>
    p === "tier1" ? "text-red-400 bg-red-500/10 border-red-500/20" :
    p === "tier2" ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
    "text-purple-400 bg-purple-500/10 border-purple-500/20"

  return (
    <div>
      <div className="px-5 py-3 flex items-center gap-2 bg-white/[0.02] border-b border-white/[0.06]">
        <Info className="w-3.5 h-3.5 text-orange-400" />
        <p className="text-xs font-semibold text-orange-400 uppercase tracking-wider">
          {prompts.length} batch{prompts.length !== 1 ? "es" : ""} sent to LLM
        </p>
        <span className="text-[11px] text-muted-foreground">
          · Expand each batch to see the exact system + user prompt
        </span>
      </div>

      <div className="divide-y divide-white/[0.04]">
        {prompts.map((p, i) => (
          <div key={i}>
            <button
              onClick={() => setOpenIdx(openIdx === i ? null : i)}
              className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-white/[0.03] transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded border", passColor(p.pass))}>
                  {passLabel(p.pass)}
                </span>
                <span className="text-xs text-muted-foreground">
                  Batch {p.batch} · {p.cell_count} cell{p.cell_count !== 1 ? "s" : ""}
                </span>
                <span className="text-[11px] text-white/25 font-mono truncate max-w-[300px]">
                  {p.cell_refs.slice(0, 4).join(", ")}{p.cell_refs.length > 4 ? ` +${p.cell_refs.length - 4}` : ""}
                </span>
              </div>
              <ChevronDown className={cn("w-4 h-4 text-muted-foreground transition-transform shrink-0", openIdx === i && "rotate-180")} />
            </button>

            {openIdx === i && (
              <div className="px-5 pb-4 flex flex-col gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    System Prompt
                  </p>
                  <pre className="text-[11px] text-foreground/70 leading-relaxed bg-white/[0.03] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono border border-white/[0.05]">
                    {p.system_prompt}
                  </pre>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    User Prompt
                  </p>
                  <pre className="text-[11px] text-foreground/70 leading-relaxed bg-white/[0.03] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono border border-white/[0.05] max-h-[360px] overflow-y-auto">
                    {p.user_prompt}
                  </pre>
                </div>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Raw LLM Response
                  </p>
                  {p.raw_response ? (
                    <pre className="text-[11px] leading-relaxed bg-orange-500/[0.05] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono border border-orange-500/[0.15] text-orange-200/80 max-h-[400px] overflow-y-auto">
                      {p.raw_response}
                    </pre>
                  ) : (
                    <p className="text-[11px] text-muted-foreground italic">
                      Not captured — re-run the model to record raw responses.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Stat chip ─────────────────────────────────────────────────────────────────

function StatChip({ label, value, textClass }: { label: string; value: string | number; textClass: string }) {
  return (
    <div className="flex items-center gap-1 bg-white/5 rounded px-2 py-0.5">
      <span className="text-[10px] text-muted-foreground leading-none">{label}</span>
      <span className={cn("text-[11px] font-semibold leading-none tabular-nums", textClass)}>{value}</span>
    </div>
  )
}

// ── Step row (left sidebar) ───────────────────────────────────────────────────

interface IStepRowProps {
  step: IPipelineStep
  data: IStepData
  isSelected: boolean
  isFailed?: boolean
  isSkipped?: boolean
  onClick: () => void
}

// Status-based colour helpers — consistent across all steps
const STATUS_TEXT  = { ready: "text-emerald-400", failed: "text-red-400",   other: "text-white/25" }
const STATUS_BG    = { ready: "bg-emerald-500/15", failed: "bg-red-500/15",  other: "bg-white/5" }
const STATUS_BADGE = { ready: "bg-emerald-500/15 text-emerald-400", failed: "bg-red-500/15 text-red-400", other: "bg-white/5 text-white/20" }

function stepStatusKey(isReady: boolean, isFailed?: boolean): "ready" | "failed" | "other" {
  if (isReady)  return "ready"
  if (isFailed) return "failed"
  return "other"
}

function StepRow({ step, data, isSelected, isFailed, isSkipped, onClick }: IStepRowProps) {
  const isReady   = data.status === "ready"
  const isLoading = data.status === "loading"
  // treat data.status === "failed" the same as isFailed prop
  const stepFailed = isFailed || data.status === "failed"
  const isPending = data.status === "pending" && !stepFailed && !isSkipped
  const [infoOpen, setInfoOpen] = useState(false)
  const isClickable = isReady || stepFailed
  const sk = stepStatusKey(isReady, stepFailed)

  return (
    <div className={cn(
      "border-l-[3px] transition-all duration-150",
      isSelected && stepFailed ? "bg-red-500/[0.05] border-l-red-500"
      : isSelected && isReady  ? "bg-emerald-500/[0.05] border-l-emerald-500"
      : isClickable             ? "border-l-transparent hover:bg-white/[0.03] hover:border-l-white/15"
      : "border-l-transparent"
    )}>
      <button
        onClick={onClick}
        disabled={!isClickable}
        className={cn(
          "w-full text-left px-4 pt-4 pb-3 focus-visible:outline-none",
          isClickable ? "cursor-pointer" : "cursor-default"
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            {/* Step number badge — colour = status */}
            <div className={cn(
              "w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-bold shrink-0 mt-0.5",
              STATUS_BADGE[sk]
            )}>
              {step.id}
            </div>

            <div className="min-w-0">
              <p className={cn(
                "text-sm font-semibold leading-tight",
                isReady ? "text-foreground" : stepFailed ? "text-red-400" : "text-white/30"
              )}>
                {step.name}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{step.description}</p>

              {stepFailed && (
                <p className="text-[11px] text-red-400/80 mt-1">LLM errors detected in this step</p>
              )}

              {/* Stats chips — show even for failed step so row count is visible */}
              {(isReady || stepFailed) && data.stats.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {data.stats.slice(0, 4).map((stat) => (
                    <StatChip key={stat.label} label={stat.label} value={stat.value} textClass={STATUS_TEXT[sk]} />
                  ))}
                  {data.stats.length > 4 && (
                    <span className="text-[10px] text-muted-foreground self-center">+{data.stats.length - 4}</span>
                  )}
                </div>
              )}

              {/* Loading skeleton */}
              {isLoading && (
                <div className="flex gap-1.5 mt-2">
                  {[56, 44, 52].map((w) => (
                    <div key={w} className="h-5 rounded bg-white/5 animate-pulse" style={{ width: w }} />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Status icon */}
          <div className="shrink-0 flex flex-col items-end gap-1 mt-0.5">
            {isReady    && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
            {isLoading  && <Loader2 className="w-4 h-4 text-white/30 animate-spin" />}
            {isPending  && <Clock className="w-4 h-4 text-white/15" />}
            {stepFailed && <AlertCircle className="w-4 h-4 text-red-400" />}
            {isSkipped  && <Minus className="w-3.5 h-3.5 text-white/10" />}
            {isReady && (
              <span className="text-[10px] text-white/30 tabular-nums">{data.rows.length.toLocaleString()} rows</span>
            )}
            {isSelected && isReady && <ChevronRight className="w-3 h-3 mt-1 text-emerald-400" />}
          </div>
        </div>
      </button>

      {/* What does this step do? */}
      {(isReady || stepFailed) && (
        <div className="px-4 pb-3">
          <button
            onClick={(e) => { e.stopPropagation(); setInfoOpen((o) => !o) }}
            className={cn(
              "flex items-center gap-1 text-[10px] transition-colors cursor-pointer focus-visible:outline-none rounded",
              infoOpen ? cn("font-medium", STATUS_TEXT[sk]) : "text-white/25 hover:text-white/50"
            )}
          >
            <Info className="w-3 h-3" />
            {infoOpen ? "Hide explanation" : "What does this step do?"}
          </button>
        </div>
      )}

      {infoOpen && (
        <div className={cn("mx-4 mb-4 rounded-lg px-3.5 py-3 border border-white/[0.06]", STATUS_BG[sk])}>
          <p className={cn("text-[11px] font-semibold uppercase tracking-wider mb-1.5", STATUS_TEXT[sk])}>
            Stage {step.id} of {PIPELINE_STEPS.length}
          </p>
          <p className="text-xs text-foreground/70 leading-relaxed">{step.explanation}</p>
        </div>
      )}
    </div>
  )
}

// ── Failed step panel ─────────────────────────────────────────────────────────

interface IFailedStepPanelProps {
  step: IPipelineStep
  error: string
  onClose: () => void
}

function FailedStepPanel({ step, error, onClose }: IFailedStepPanelProps) {
  return (
    <div className="rounded-xl border border-red-500/20 bg-[#13161f] flex flex-col h-full shadow-xl shadow-black/40">
      <div className="flex items-center justify-between px-5 py-4 border-b border-red-500/10 gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center text-[11px] font-bold shrink-0 text-red-400">
            {step.id}
          </div>
          <div>
            <p className="text-sm font-semibold text-red-400">{step.name}</p>
            <p className="text-[11px] text-muted-foreground">Pipeline failed at this step</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-white/10 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-8 gap-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-red-400" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground mb-2">Error at Step {step.id} — {step.name}</p>
          <p className="text-xs text-muted-foreground mb-4 max-w-md leading-relaxed">{step.explanation}</p>
        </div>
        <div className="w-full max-w-lg text-left">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-red-400/70 mb-2">Error details</p>
          <pre className="text-xs text-red-300/80 bg-red-500/[0.06] border border-red-500/15 rounded-lg p-4 whitespace-pre-wrap break-words font-mono leading-relaxed">
            {error}
          </pre>
        </div>
        <p className="text-[11px] text-muted-foreground/50">
          Steps before this point completed successfully — select them in the left panel to inspect their data.
        </p>
      </div>
    </div>
  )
}

// ── Empty right-panel state ───────────────────────────────────────────────────

function EmptyDetailState({ readyCount }: { readyCount: number }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#13161f] flex flex-col items-center justify-center h-full gap-4 text-center">
      <div className="w-14 h-14 rounded-2xl bg-white/[0.04] border border-white/10 flex items-center justify-center">
        <BarChart2 className="w-7 h-7 text-white/15" />
      </div>
      {readyCount > 0 ? (
        <>
          <p className="text-sm font-medium text-muted-foreground">Select a stage to inspect</p>
          <p className="text-xs text-white/25">Click any completed stage on the left to view its data</p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-muted-foreground">Waiting for pipeline to start</p>
          <p className="text-xs text-white/25">Stage files will appear here as the pipeline runs</p>
        </>
      )}
    </div>
  )
}

// ── Detail table panel ────────────────────────────────────────────────────────

interface IDetailPanelProps {
  step: IPipelineStep
  data: IStepData
  onClose: () => void
  prompts?: IPromptRecord[] | null
}

// Columns that should stay compact (IDs, enums, short codes)
const COMPACT_COLS = new Set([
  "sheet", "cell", "tier", "severity", "is_terminal", "is_formula",
  "symbol", "pass", "batch", "cell_count", "instance_count",
  "risk_score", "pattern_instance_count", "out_degree", "in_degree",
])

function DetailPanel({ step, data, onClose, prompts }: IDetailPanelProps) {
  const [sortCol,      setSortCol]      = useState<string | null>(null)
  const [sortAsc,      setSortAsc]      = useState(true)
  const [filter,       setFilter]       = useState("")
  const [page,         setPage]         = useState(0)
  const [showExplain,  setShowExplain]  = useState(true)
  const [activeTab,    setActiveTab]    = useState<"table" | "prompts">("table")
  const PAGE_SIZE = 100


  const filtered = filter
    ? data.rows.filter((row) =>
        Object.values(row).some((v) => v.toLowerCase().includes(filter.toLowerCase()))
      )
    : data.rows

  const sorted = sortCol
    ? [...filtered].sort((a, b) => {
        const av = a[sortCol] ?? ""
        const bv = b[sortCol] ?? ""
        const numA = parseFloat(av)
        const numB = parseFloat(bv)
        const cmp = !isNaN(numA) && !isNaN(numB) ? numA - numB : av.localeCompare(bv)
        return sortAsc ? cmp : -cmp
      })
    : filtered

  const pageRows   = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)

  const handleSort = (col: string) => {
    if (sortCol === col) setSortAsc((a) => !a)
    else { setSortCol(col); setSortAsc(true) }
    setPage(0)
  }

  return (
    <div className="rounded-xl border border-white/10 bg-[#13161f] flex flex-col h-full shadow-xl shadow-black/40">
      {/* Panel header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0",
            STATUS_BADGE["ready"]
          )}>
            {step.id}
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{step.name}</p>
            <p className="text-[11px] text-muted-foreground">
              {sorted.length.toLocaleString()} rows · {data.headers.length} columns
              {filter && ` · filtered from ${data.rows.length.toLocaleString()}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 ml-auto">
          {/* All stats */}
          <div className="hidden xl:flex gap-1 flex-wrap max-w-sm">
            {data.stats.map((stat) => (
              <StatChip key={stat.label} label={stat.label} value={stat.value} textClass={STATUS_TEXT["ready"]} />
            ))}
          </div>

          {/* Filter */}
          <input
            type="text"
            value={filter}
            onChange={(e) => { setFilter(e.target.value); setPage(0) }}
            placeholder="Filter rows…"
            className="h-7 w-40 rounded-md bg-white/5 border border-white/10 text-xs px-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-white/20"
          />

          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Stage explanation */}
      {showExplain && (
        <div className={cn("px-5 py-4 border-b border-white/[0.06]", STATUS_BG["ready"])}>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className={cn("text-[10px] font-semibold uppercase tracking-widest mb-2", STATUS_TEXT["ready"])}>
                Stage {step.id} of {PIPELINE_STEPS.length} — What this step does
              </p>
              <p className="text-sm text-foreground/75 leading-relaxed max-w-2xl">
                {step.explanation}
              </p>
            </div>
            <button
              onClick={() => setShowExplain(false)}
              className="shrink-0 mt-0.5 w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 transition-colors cursor-pointer"
            >
              <X className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          </div>
        </div>
      )}

      {/* Restore explanation link when dismissed */}
      {!showExplain && (
        <button
          onClick={() => setShowExplain(true)}
          className={cn(
            "w-full px-5 py-2 text-left text-[11px] border-b border-white/[0.06]",
            "transition-colors cursor-pointer hover:bg-white/[0.03]",
            STATUS_TEXT["ready"]
          )}
        >
          <Info className="w-3 h-3 inline mr-1.5 -mt-px" />
          Show stage explanation
        </button>
      )}

      {/* Stats row for smaller screens */}
      {data.stats.length > 0 && (
        <div className="xl:hidden flex flex-wrap gap-1 px-5 py-2.5 border-b border-white/[0.06]">
          {data.stats.map((stat) => (
            <StatChip key={stat.label} label={stat.label} value={stat.value} textClass={STATUS_TEXT["ready"]} />
          ))}
        </div>
      )}

      {/* Tab bar — prompts prop is undefined for non-step-11, null/array for step-11 */}
      {prompts !== undefined && (
        <div className="flex border-b border-white/[0.06] shrink-0 px-5">
          <button
            onClick={() => setActiveTab("table")}
            className={cn(
              "py-2.5 px-1 mr-5 text-xs font-semibold border-b-2 transition-colors cursor-pointer",
              activeTab === "table"
                ? cn("border-current", STATUS_TEXT["ready"])
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            Issues Table
            <span className="ml-1.5 text-[10px] opacity-60">({sorted.length})</span>
          </button>
          <button
            onClick={() => setActiveTab("prompts")}
            className={cn(
              "py-2.5 px-1 text-xs font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5",
              activeTab === "prompts"
                ? cn("border-current", STATUS_TEXT["ready"])
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            LLM Prompts
            {prompts && prompts.length > 0 ? (
              <span className="px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[10px] font-bold">
                {prompts.length} batch{prompts.length !== 1 ? "es" : ""}
              </span>
            ) : (
              <span className="text-[10px] opacity-40">(loading…)</span>
            )}
          </button>
        </div>
      )}

      {/* Table view */}
      {activeTab === "table" && (
        <>
          <div className="overflow-auto flex-1 min-h-0">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="sticky top-0 z-10 bg-[#0f1117]">
                  {data.headers.map((h) => (
                    <th
                      key={h}
                      onClick={() => handleSort(h)}
                      className="text-left px-3 py-2.5 font-semibold text-muted-foreground border-b border-white/10 whitespace-nowrap cursor-pointer hover:text-foreground select-none"
                    >
                      {h}
                      {sortCol === h && <span className="ml-1 opacity-60">{sortAsc ? "↑" : "↓"}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, ri) => (
                  <tr key={ri} className="border-b border-white/[0.04] hover:bg-white/[0.025] transition-colors">
                    {data.headers.map((h) => (
                      <td
                        key={h}
                        className={cn(
                          "px-3 py-2 text-foreground/80 font-mono align-top",
                          COMPACT_COLS.has(h) ? "whitespace-nowrap" : "break-words whitespace-pre-wrap max-w-[420px]"
                        )}
                      >
                        {h === "severity" ? (
                          <span className={cn(
                            "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                            row[h] === "CRITICAL" && "bg-red-500/20 text-red-400",
                            row[h] === "WARNING"  && "bg-amber-500/20 text-amber-400",
                            row[h] === "INFO"     && "bg-blue-500/20 text-blue-400",
                          )}>
                            {row[h]}
                          </span>
                        ) : h === "tier" ? (
                          <span className={cn(
                            "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                            row[h] === "1"    && "bg-red-500/20 text-red-400",
                            row[h] === "2"    && "bg-amber-500/20 text-amber-400",
                            row[h] === "3"    && "bg-emerald-500/20 text-emerald-400",
                            row[h] === "AUTO" && "bg-white/10 text-muted-foreground",
                          )}>
                            {row[h] === "AUTO" ? "AUTO" : row[h] ? `T${row[h]}` : ""}
                          </span>
                        ) : h === "is_terminal" || h === "is_formula" ? (
                          <span className={cn("text-[10px]", row[h] === "True" ? "text-emerald-400" : "text-white/30")}>
                            {row[h]}
                          </span>
                        ) : (
                          row[h]
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-white/10 text-xs text-muted-foreground shrink-0">
              <span>
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sorted.length)} of {sorted.length.toLocaleString()}
              </span>
              <div className="flex gap-1.5">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 cursor-pointer disabled:cursor-default"
                >
                  Prev
                </button>
                <span className="px-2 py-1 text-white/40">{page + 1} / {totalPages}</span>
                <button
                  disabled={page === totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 cursor-pointer disabled:cursor-default"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Prompts view */}
      {activeTab === "prompts" && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          {prompts && prompts.length > 0 ? (
            <PromptsSection prompts={prompts} />
          ) : (
            <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
              Loading prompt records…
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PipelinePage(props: IPageProps) {
  const { params }  = props
  const { jobId }   = use(params)
  const router      = useRouter()

  const statusQuery = useJobStatus({ jobId })
  const status      = statusQuery.data
  const jobComplete = status?.status === "completed" || status?.status === "failed"

  const { stepData, readyCount, loadedCount, failedCount, total, firstPollDone } = usePipelineData({ jobId, jobComplete })
  // "summary" = executive summary panel; step id string = stage detail
  const [selectedId, setSelectedId]     = useState<string>("summary")
  const [pastRuns,   setPastRuns]       = useState<IPastRun[]>([])
  const [prompts,    setPrompts]        = useState<IPromptRecord[] | null>(null)

  const selectedStep = selectedId !== "summary"
    ? PIPELINE_STEPS.find((s) => s.id === selectedId) ?? null
    : null
  const selectedData = selectedId !== "summary" ? stepData[selectedId] : null

  const handleRowClick = (id: string) => {
    if (id === "summary") { setSelectedId("summary"); return }
    if (id === failedStepId) { setSelectedId(id); return }
    if (stepData[id]?.status !== "ready") return
    setSelectedId((prev) => (prev === id ? "summary" : id))
  }

  // Fetch LLM prompts when step 11 is opened
  useEffect(() => {
    if (selectedId !== "11") { setPrompts(null); return }
    fetch(`/api/interim/${jobId}/11_llm_prompts.json`)
      .then(r => r.ok ? r.json() : null)
      .then(data => setPrompts(Array.isArray(data) ? data : null))
      .catch(() => setPrompts(null))
  }, [selectedId, jobId])

  useEffect(() => {
    fetch("/api/interim")
      .then((r) => r.json())
      .then((data) => setPastRuns(data.jobs ?? []))
      .catch(() => {})
  }, [])

  // Ensure current job always appears in the selector
  const runOptions: IPastRun[] = pastRuns.some((r) => r.job_id === jobId)
    ? pastRuns
    : [{ job_id: jobId, file_count: readyCount, model_filename: null, started_at: null }, ...pastRuns]

  const currentRun   = runOptions.find((r) => r.job_id === jobId)
  const modelName    = currentRun?.model_filename ?? null

  // Label shown in the run selector dropdown
  const runLabel = (run: IPastRun) => {
    const name = run.model_filename ?? run.job_id.slice(0, 8) + "…"
    return `${run.job_id === jobId ? "▸ " : ""}${name} · ${run.file_count} stages`
  }

  const isRunning      = status?.status === "running" || status?.status === "pending"
  const isFailed       = status?.status === "failed"
  const anyStepFailed  = failedCount > 0
  const effectiveFailed = isFailed || anyStepFailed
  const allLoaded      = loadedCount === total && total > 0

  // Step with status="failed" (LLM error detected), or first non-loaded step when job failed
  const failedStepId = anyStepFailed
    ? PIPELINE_STEPS.find((s) => stepData[s.id]?.status === "failed")?.id ?? null
    : (isFailed && firstPollDone)
      ? PIPELINE_STEPS.find((s) => stepData[s.id]?.status !== "ready")?.id ?? null
      : null
  const failedStepIndex = failedStepId
    ? PIPELINE_STEPS.findIndex((s) => s.id === failedStepId)
    : -1
  const skippedStepIds = new Set(
    failedStepIndex >= 0
      ? PIPELINE_STEPS.slice(failedStepIndex + 1).map((s) => s.id)
      : []
  )

  // Auto-select the failed step so users see the error immediately
  useEffect(() => {
    if (failedStepId && selectedId === "summary") setSelectedId(failedStepId)
  }, [failedStepId]) // eslint-disable-line react-hooks/exhaustive-deps
  // 100% when all files loaded; use backend progress while running; file ratio otherwise
  const execProgress = status?.progress ?? 0
  const progressPct  = total > 0 ? Math.round((loadedCount / total) * 100) : 0
  const displayPct   = allLoaded ? 100 : isRunning ? execProgress : progressPct

  return (
    <main className="h-screen bg-[#0f1117] flex flex-col overflow-hidden">

      {/* ── Fixed-height top bar ────────────────────────────────────────────── */}
      <div className="border-b border-white/[0.06] bg-[#0f1117] shrink-0">
        <div className="max-w-[1400px] mx-auto px-6 py-3.5 flex items-center justify-between gap-4 flex-wrap">
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            New review
          </button>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Past runs selector */}
            {runOptions.length > 1 && (
              <div className="flex items-center gap-2">
                <History className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <select
                  value={jobId}
                  onChange={(e) => router.push(`/results/${e.target.value}/pipeline`)}
                  className="text-xs bg-white/5 border border-white/10 rounded-md px-2.5 py-1.5 text-muted-foreground hover:border-white/20 focus:outline-none focus:border-white/30 cursor-pointer max-w-[260px]"
                >
                  {runOptions.map((run) => (
                    <option key={run.job_id} value={run.job_id} className="bg-[#1a1f2e]">
                      {runLabel(run)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* View full report — only when complete without failures */}
            {jobComplete && !effectiveFailed && (
              <button
                onClick={() => router.push(`/results/${jobId}`)}
                className="text-xs text-muted-foreground hover:text-foreground border border-white/10 hover:border-white/20 rounded-md px-3 py-1.5 transition-colors cursor-pointer"
              >
                View full report
              </button>
            )}

            {status && (
              <Badge variant="outline" className={cn(
                "text-xs",
                effectiveFailed                             && "border-red-500/40 text-red-400",
                !effectiveFailed && status.status === "completed" && "border-emerald-500/40 text-emerald-400",
                status.status === "running"                 && "border-amber-500/40 text-amber-400",
                !effectiveFailed && status.status === "pending"   && "border-white/20 text-muted-foreground",
              )}>
                {effectiveFailed && status.status === "completed" ? "failed" : status.status}
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* ── Page header + progress ───────────────────────────────────────────── */}
      <div className="border-b border-white/[0.04] shrink-0">
        <div className="max-w-[1400px] mx-auto px-6 pt-5 pb-4">
          {/* Title row */}
          <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Pipeline Inspector
              </p>
              <h1 className="text-xl font-bold tracking-tight text-foreground mt-0.5">
                {modelName ?? "Stage-by-Stage Analysis"}
              </h1>
              {modelName && (
                <p className="text-[11px] text-muted-foreground mt-1 font-mono">{jobId}</p>
              )}
            </div>
            {/* Stage file count badge */}
            <div className="text-right shrink-0">
              <p className={cn("text-xs font-semibold tabular-nums",
                effectiveFailed ? "text-red-400" : jobComplete ? "text-emerald-400" : "text-amber-400"
              )}>
                {loadedCount}/{total} stages ready
              </p>
            </div>
          </div>

          {/* Progress bar + step label */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-3">
              <Progress
                value={displayPct}
                className={cn("h-1.5 flex-1 bg-white/10", isRunning && "animate-pulse")}
              />
              <span className="text-xs text-muted-foreground tabular-nums shrink-0 w-9 text-right">
                {displayPct}%
              </span>
            </div>
            {isRunning && status?.step && (
              <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin shrink-0" />
                {status.step}
              </p>
            )}
            {isFailed && (
              <p className="text-[11px] text-red-400">{status?.error ?? "Pipeline failed"}</p>
            )}
            {anyStepFailed && !isFailed && (
              <p className="text-[11px] text-red-400">
                {failedCount === 1 ? "1 step" : `${failedCount} steps`} failed — check the highlighted stage
              </p>
            )}
            {allLoaded && !effectiveFailed && (
              <p className="text-[11px] text-emerald-400">All pipeline steps complete</p>
            )}
          </div>
        </div>
      </div>

      {/* ── Two-column body — fills remaining viewport height ───────────────── */}
      <div className="flex-1 flex overflow-hidden max-w-[1400px] w-full mx-auto px-6 py-4 gap-4">

          {/* Left: step list — independently scrollable */}
          <div className="w-72 xl:w-80 shrink-0 flex flex-col">
            <div className="rounded-xl border border-white/10 bg-[#13161f] flex flex-col overflow-hidden flex-1 min-h-0">
              {/* List header — pinned */}
              <div className="px-4 py-3 flex items-center justify-between shrink-0 border-b border-white/[0.05]">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Stages
                </p>
                <div className="flex items-center gap-1.5">
                  <span className={cn(
                    "w-1.5 h-1.5 rounded-full",
                    effectiveFailed ? "bg-red-400" : loadedCount === total ? "bg-emerald-400" : "bg-amber-400 animate-pulse"
                  )} />
                  <span className="text-[10px] text-muted-foreground">
                    {loadedCount}/{total} ready
                  </span>
                </div>
              </div>

              {/* Step rows — scrollable */}
              <div className="overflow-y-auto divide-y divide-white/[0.04]">
                {/* Summary row — always first */}
                <button
                  onClick={() => handleRowClick("summary")}
                  className={cn(
                    "w-full text-left px-4 py-4 border-l-[3px] transition-all duration-150 cursor-pointer focus-visible:outline-none",
                    selectedId === "summary"
                      ? "border-l-white/40 bg-white/[0.06]"
                      : "border-l-transparent hover:bg-white/[0.03] hover:border-l-white/15"
                  )}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center shrink-0">
                        <Layers className="w-3.5 h-3.5 text-white/60" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground leading-tight">Executive Summary</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">Risk indicators at a glance</p>
                      </div>
                    </div>
                    {selectedId === "summary"
                      ? <ChevronRight className="w-3.5 h-3.5 text-white/40 shrink-0" />
                      : <BarChart2 className="w-3.5 h-3.5 text-white/20 shrink-0" />
                    }
                  </div>
                </button>

                {PIPELINE_STEPS.map((step) => (
                  <StepRow
                    key={step.id}
                    step={step}
                    data={stepData[step.id]}
                    isSelected={selectedId === step.id}
                    isFailed={step.id === failedStepId}
                    isSkipped={skippedStepIds.has(step.id)}
                    onClick={() => handleRowClick(step.id)}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Right: detail panel — fills remaining height, no page scroll */}
          <div className="flex-1 min-w-0 flex flex-col min-h-0">
            {selectedId === "summary" ? (
              <SummaryPanel stepData={stepData} modelName={modelName} />
            ) : selectedStep && selectedData?.status === "ready" ? (
              <DetailPanel
                step={selectedStep}
                data={selectedData}
                onClose={() => setSelectedId("summary")}
                {...(selectedId === "11" ? { prompts } : {})}
              />
            ) : selectedId === failedStepId && failedStepId ? (
              <FailedStepPanel
                step={PIPELINE_STEPS.find((s) => s.id === failedStepId)!}
                error={stepData[failedStepId]?.error ?? status?.error ?? "An unexpected error occurred during this step."}
                onClose={() => setSelectedId("summary")}
              />
            ) : (
              <EmptyDetailState readyCount={readyCount} />
            )}
          </div>

      </div>
    </main>
  )
}
