"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import TierBreakdown from "@/components/TierBreakdown";
import { formatDate } from "@/lib/utils";
import type { IReport } from "@/lib/types";

interface IStat {
  label: string;
  value: string | number;
  colorClass?: string;
}

const StatCell = (props: IStat) => {
  const { label, value, colorClass } = props;
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${colorClass ?? "text-foreground"}`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
    </div>
  );
};

interface ISummaryCard {
  report: IReport;
}

// Input: full IReport
// Output: summary card with issue counts, tier breakdown, and file metadata
const SummaryCard = (props: ISummaryCard) => {
  const { report } = props;
  const { summary, model_filename, map_filename, reviewed_at } = report;

  const symbolOrder = ["F", "S", "C", "N", "X"] as const;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

      {/* Issues overview */}
      <Card className="lg:col-span-1">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Issues Found
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid grid-cols-3 gap-4">
            <StatCell
              label="Critical"
              value={summary.critical}
              colorClass="text-[var(--sev-critical-fg)]"
            />
            <StatCell
              label="Warning"
              value={summary.warning}
              colorClass="text-[var(--sev-warning-fg)]"
            />
            <StatCell
              label="Info"
              value={summary.info}
              colorClass="text-[var(--sev-info-fg)]"
            />
          </div>

          <Separator />

          <StatCell
            label="Cells affected by issues"
            value={summary.cells_affected_by_issues}
          />

          <Separator />

          {/* Symbol breakdown */}
          <div>
            <p className="text-xs text-muted-foreground mb-2">Symbol breakdown</p>
            <div className="flex gap-2 flex-wrap">
              {symbolOrder.map((sym) => {
                const count = summary.symbol_breakdown[sym];
                if (!count) return null;
                return (
                  <div key={sym} className="flex items-center gap-1.5 text-xs">
                    <span className="font-mono font-semibold text-foreground">{sym}</span>
                    <span className="text-muted-foreground">{count.toLocaleString()}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tier breakdown */}
      <Card className="lg:col-span-1">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Review Tiers
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TierBreakdown
            tiers={summary.tier_breakdown}
            llmCalls={summary.llm_calls_made}
            patternsReviewed={summary.patterns_reviewed}
          />
        </CardContent>
      </Card>

      {/* File metadata */}
      <Card className="lg:col-span-1">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Review Metadata
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-0.5">
            <p className="text-xs text-muted-foreground">Model file</p>
            <p className="text-sm font-medium text-foreground font-mono break-all">
              {model_filename}
            </p>
          </div>
          <div className="flex flex-col gap-0.5">
            <p className="text-xs text-muted-foreground">Map file</p>
            <p className="text-sm font-medium text-foreground font-mono break-all">
              {map_filename}
            </p>
          </div>
          <Separator />
          <div className="flex flex-col gap-0.5">
            <p className="text-xs text-muted-foreground">Reviewed at</p>
            <p className="text-sm font-medium text-foreground">{formatDate(reviewed_at)}</p>
          </div>
        </CardContent>
      </Card>

    </div>
  );
};

export default SummaryCard;
