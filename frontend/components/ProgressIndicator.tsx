"use client";

import { Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { IStatusResp, JobStatus } from "@/lib/types";

// Pipeline step labels shown during processing
const STEP_LABELS: Record<string, string> = {
  parsing_map:       "Parsing map file",
  parsing_model:     "Parsing model file",
  detecting_structure: "Detecting sheet structure",
  building_graph:    "Building dependency graph",
  scoring_risk:      "Scoring cell risk",
  assigning_tiers:   "Assigning tiers",
  auto_flagging:     "Auto-flagging N and X cells",
  tier3_checks:      "Running Tier 3 rule checks",
  deduplicating:     "Deduplicating formula patterns",
  enriching:         "Enriching context",
  llm_review:        "Running LLM review",
  propagating:       "Propagating pattern findings",
  generating_report: "Generating report",
  completed:         "Complete",
};

const STATUS_ICONS: Record<JobStatus, React.ReactNode> = {
  pending:    <Clock className="w-5 h-5 text-muted-foreground" />,
  processing: <Loader2 className="w-5 h-5 text-primary animate-spin" />,
  completed:  <CheckCircle2 className="w-5 h-5 text-[var(--tier3-fg)]" />,
  failed:     <XCircle className="w-5 h-5 text-[var(--sev-critical-fg)]" />,
};

// Maps step name to a rough % for the progress bar
const stepToPercent = (step: string | undefined): number => {
  const steps = Object.keys(STEP_LABELS);
  const idx = steps.indexOf(step ?? "");
  if (idx < 0) return 5;
  return Math.round(((idx + 1) / steps.length) * 95);
};

interface IProgressIndicator {
  status: IStatusResp;
}

// Input: IStatusResp (status, step, progress, error)
// Output: animated progress bar with current pipeline step label
const ProgressIndicator = (props: IProgressIndicator) => {
  const { status } = props;
  const { status: jobStatus, step, progress, error } = status;

  const percent = jobStatus === "completed" ? 100 : stepToPercent(step);
  const stepLabel = STEP_LABELS[step ?? ""] ?? progress ?? "Initialising...";

  return (
    <div className="flex flex-col gap-4 w-full">
      <div className="flex items-center gap-3">
        {STATUS_ICONS[jobStatus]}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground">
            {jobStatus === "completed" && "Analysis complete"}
            {jobStatus === "failed" && "Analysis failed"}
            {jobStatus === "pending" && "Queued — waiting to start"}
            {jobStatus === "processing" && stepLabel}
          </p>
          {jobStatus === "failed" && error && (
            <p className="text-xs text-[var(--sev-critical-fg)] mt-0.5">{error}</p>
          )}
        </div>
        <span
          className={cn(
            "text-xs font-mono tabular-nums",
            jobStatus === "completed" ? "text-[var(--tier3-fg)]" : "text-muted-foreground"
          )}
        >
          {percent}%
        </span>
      </div>

      <Progress
        value={percent}
        className={cn(
          "h-1.5",
          jobStatus === "failed" && "[&>div]:bg-[var(--sev-critical-fg)]",
          jobStatus === "completed" && "[&>div]:bg-[var(--tier3-fg)]"
        )}
      />
    </div>
  );
};

export default ProgressIndicator;
