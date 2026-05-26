"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { IIssue, Severity, Symbol, Tier } from "@/lib/types";

// Severity badge colours
const SEVERITY_CLASS: Record<Severity, string> = {
  CRITICAL: "bg-[var(--sev-critical-bg)] text-[var(--sev-critical-fg)] border-[var(--sev-critical-border)]",
  WARNING:  "bg-[var(--sev-warning-bg)] text-[var(--sev-warning-fg)] border-[var(--sev-warning-border)]",
  INFO:     "bg-[var(--sev-info-bg)] text-[var(--sev-info-fg)] border-[var(--sev-info-border)]",
};

// Tier badge colours
const TIER_CLASS: Record<string, string> = {
  "1":    "text-[var(--tier1-fg)]",
  "2":    "text-[var(--tier2-fg)]",
  "3":    "text-[var(--tier3-fg)]",
  "AUTO": "text-[var(--auto-fg)]",
};

const SYMBOL_LABELS: Record<Symbol, string> = {
  F: "Formula",
  S: "Sum",
  C: "Callup",
  N: "Hardcoded",
  X: "External",
};

interface IExpandedInstances {
  instances: string[];
}

const ExpandedInstances = (props: IExpandedInstances) => {
  const { instances } = props;
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {instances.map((cell) => (
        <span
          key={cell}
          className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
        >
          {cell}
        </span>
      ))}
    </div>
  );
};

interface IIssueRow {
  issue: IIssue;
}

const IssueRow = (props: IIssueRow) => {
  const { issue } = props;
  const [expanded, setExpanded] = useState(false);
  const hasMultiple = issue.instance_count > 1;

  return (
    <TableRow className="align-top">
      <TableCell className="font-mono text-xs text-muted-foreground whitespace-nowrap">
        {issue.sheet}
      </TableCell>
      <TableCell className="font-mono text-xs font-semibold whitespace-nowrap">
        {issue.cell}
      </TableCell>
      <TableCell className="text-xs max-w-[140px]">
        <span className="truncate block" title={issue.label}>{issue.label}</span>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs font-mono">
          {issue.symbol}
        </Badge>
      </TableCell>
      <TableCell>
        <span className={cn("text-xs font-semibold", TIER_CLASS[String(issue.tier)])}>
          {issue.tier === "AUTO" ? "Auto" : `T${issue.tier}`}
        </span>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
        {issue.period ?? "—"}
      </TableCell>
      <TableCell>
        <span className="text-xs font-mono text-muted-foreground">{issue.issue_type}</span>
      </TableCell>
      <TableCell>
        <span className={cn("text-xs font-semibold px-2 py-0.5 rounded border", SEVERITY_CLASS[issue.severity])}>
          {issue.severity}
        </span>
      </TableCell>
      <TableCell className="text-xs max-w-[220px]">
        <p className="text-foreground">{issue.description}</p>
        {issue.suggested_fix && (
          <p className="text-muted-foreground mt-1 italic">{issue.suggested_fix}</p>
        )}
      </TableCell>
      <TableCell>
        {hasMultiple ? (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
          >
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            {issue.instance_count} cells
          </button>
        ) : (
          <span className="text-xs text-muted-foreground">1 cell</span>
        )}
        {expanded && <ExpandedInstances instances={issue.instances} />}
      </TableCell>
    </TableRow>
  );
};

type TierFilter = "all" | "1" | "2" | "3" | "AUTO";
type SevFilter  = "all" | Severity;
type SymFilter  = "all" | Symbol;

interface IIssuesTable {
  issues: IIssue[];
}

// Input: flat list of IIssue
// Output: filterable table with Tier tabs, Severity filter, Symbol filter, Sheet filter
const IssuesTable = (props: IIssuesTable) => {
  const { issues } = props;

  const [tierTab, setTierTab]     = useState<TierFilter>("all");
  const [severity, setSeverity]   = useState<SevFilter>("all");
  const [symbol, setSymbol]       = useState<SymFilter>("all");
  const [sheet, setSheet]         = useState<string>("all");

  // Collect unique sheets for the dropdown
  const sheets = Array.from(new Set(issues.map((i) => i.sheet))).sort();

  const filtered = issues.filter((issue) => {
    const tierMatch = tierTab === "all" || String(issue.tier) === tierTab;
    const sevMatch  = severity === "all" || issue.severity === severity;
    const symMatch  = symbol === "all" || issue.symbol === symbol;
    const sheetMatch = sheet === "all" || issue.sheet === sheet;
    return tierMatch && sevMatch && symMatch && sheetMatch;
  });

  return (
    <div className="flex flex-col gap-4">

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <Tabs value={tierTab} onValueChange={(v) => setTierTab(v as TierFilter)}>
          <TabsList className="h-8">
            <TabsTrigger value="all" className="text-xs px-2 h-6">All</TabsTrigger>
            <TabsTrigger value="1" className="text-xs px-2 h-6 text-[var(--tier1-fg)]">Tier 1</TabsTrigger>
            <TabsTrigger value="2" className="text-xs px-2 h-6 text-[var(--tier2-fg)]">Tier 2</TabsTrigger>
            <TabsTrigger value="3" className="text-xs px-2 h-6 text-[var(--tier3-fg)]">Tier 3</TabsTrigger>
            <TabsTrigger value="AUTO" className="text-xs px-2 h-6">Auto</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex gap-2 flex-wrap sm:ml-auto">
          <Select value={severity} onValueChange={(v) => setSeverity(v as SevFilter)}>
            <SelectTrigger className="h-8 text-xs w-[120px]">
              <SelectValue placeholder="Severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All severity</SelectItem>
              <SelectItem value="CRITICAL">Critical</SelectItem>
              <SelectItem value="WARNING">Warning</SelectItem>
              <SelectItem value="INFO">Info</SelectItem>
            </SelectContent>
          </Select>

          <Select value={symbol} onValueChange={(v) => setSymbol(v as SymFilter)}>
            <SelectTrigger className="h-8 text-xs w-[110px]">
              <SelectValue placeholder="Symbol" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All symbols</SelectItem>
              {(["F", "S", "C", "N", "X"] as Symbol[]).map((s) => (
                <SelectItem key={s} value={s}>
                  {s} — {SYMBOL_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sheet} onValueChange={(v) => setSheet(v ?? "all")}>
            <SelectTrigger className="h-8 text-xs w-[130px]">
              <SelectValue placeholder="Sheet" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sheets</SelectItem>
              {sheets.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Result count */}
      <p className="text-xs text-muted-foreground">
        Showing {filtered.length} of {issues.length} issues
      </p>

      {/* Table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="text-xs">Sheet</TableHead>
              <TableHead className="text-xs">Cell</TableHead>
              <TableHead className="text-xs">Label</TableHead>
              <TableHead className="text-xs">Symbol</TableHead>
              <TableHead className="text-xs">Tier</TableHead>
              <TableHead className="text-xs">Period</TableHead>
              <TableHead className="text-xs">Issue Type</TableHead>
              <TableHead className="text-xs">Severity</TableHead>
              <TableHead className="text-xs min-w-[240px]">Description / Fix</TableHead>
              <TableHead className="text-xs">Instances</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center text-sm text-muted-foreground py-10">
                  No issues match the current filters.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((issue, idx) => (
                <IssueRow key={`${issue.sheet}-${issue.cell}-${idx}`} issue={issue} />
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default IssuesTable;
