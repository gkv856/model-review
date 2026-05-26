"use client";

import type { ITierBreak } from "@/lib/types";

interface ITierRow {
  label: string;
  count: number;
  description: string;
  colorClass: string;
}

interface ITierBreakdown {
  tiers: ITierBreak;
  llmCalls: number;
  patternsReviewed: number;
}

// Input: tier breakdown counts, llm call stats
// Output: visual tier breakdown panel showing risk distribution + LLM transparency
const TierBreakdown = (props: ITierBreakdown) => {
  const { tiers, llmCalls, patternsReviewed } = props;

  const total = tiers.tier1 + tiers.tier2 + tiers.tier3 + tiers.auto;

  const rows: ITierRow[] = [
    {
      label: "Tier 1",
      count: tiers.tier1,
      description: "Critical path — full LLM review",
      colorClass: "text-[var(--tier1-fg)] bg-[var(--tier1-fg)]/10",
    },
    {
      label: "Tier 2",
      count: tiers.tier2,
      description: "Standard formulas — lightweight LLM review",
      colorClass: "text-[var(--tier2-fg)] bg-[var(--tier2-fg)]/10",
    },
    {
      label: "Tier 3",
      count: tiers.tier3,
      description: "Low risk — rule-based checks only",
      colorClass: "text-[var(--tier3-fg)] bg-[var(--tier3-fg)]/10",
    },
    {
      label: "Auto",
      count: tiers.auto,
      description: "N and X cells — deterministic, no LLM",
      colorClass: "text-[var(--auto-fg)] bg-[var(--auto-fg)]/10",
    },
  ];

  const barWidth = (count: number): string => {
    if (total === 0) return "0%";
    return `${Math.round((count / total) * 100)}%`;
  };

  return (
    <div className="flex flex-col gap-4">
      {rows.map((row) => (
        <div key={row.label} className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${row.colorClass}`}
              >
                {row.label}
              </span>
              <span className="text-xs text-muted-foreground">{row.description}</span>
            </div>
            <span className="text-sm font-semibold text-foreground tabular-nums">
              {row.count.toLocaleString()}
            </span>
          </div>
          <div className="h-1 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${row.colorClass.split(" ")[0].replace("text-", "bg-")}`}
              style={{ width: barWidth(row.count) }}
            />
          </div>
        </div>
      ))}

      <div className="mt-2 pt-4 border-t border-border flex items-center justify-between gap-4">
        <div className="text-center">
          <p className="text-xs text-muted-foreground">LLM calls made</p>
          <p className="text-xl font-bold text-foreground tabular-nums">{llmCalls}</p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Patterns reviewed</p>
          <p className="text-xl font-bold text-foreground tabular-nums">{patternsReviewed}</p>
        </div>
        <div className="h-8 w-px bg-border" />
        <div className="text-center">
          <p className="text-xs text-muted-foreground">Total UFs</p>
          <p className="text-xl font-bold text-foreground tabular-nums">{total.toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
};

export default TierBreakdown;
