// Shared TypeScript types — Financial Model Integrity Reviewer v3

export type Severity = "CRITICAL" | "WARNING" | "INFO";
export type Symbol = "F" | "S" | "C" | "N" | "X";
export type JobStatus = "pending" | "processing" | "completed" | "failed";
export type Tier = 1 | 2 | 3 | "AUTO";

export interface IIssue {
  sheet: string;
  cell: string;
  label: string;
  symbol: Symbol;
  tier: Tier;
  section: string;
  period: string;
  formula: string;
  computed_value: number | string | null;
  issue_type: string;
  severity: Severity;
  description: string;
  suggested_fix: string;
  instances: string[];
  instance_count: number;
}

export interface IGraphCheck {
  circular_references: string[];
  broken_references: string[];
  external_links_in_chain: string[];
  hardcoded_mid_chain: string[];
}

export interface ISymbolBreak {
  F?: number;
  S?: number;
  C?: number;
  N?: number;
  X?: number;
}

export interface ITierBreak {
  tier1: number;
  tier2: number;
  tier3: number;
  auto: number;
}

export interface ISummary {
  total_ufs: number;
  symbol_breakdown: ISymbolBreak;
  tier_breakdown: ITierBreak;
  llm_calls_made: number;
  patterns_reviewed: number;
  total_issues: number;
  critical: number;
  warning: number;
  info: number;
  cells_affected_by_issues: number;
}

export interface IReport {
  job_id: string;
  model_filename: string;
  map_filename: string;
  reviewed_at: string;
  summary: ISummary;
  graph_analysis: IGraphCheck;
  issues: IIssue[];
}

export interface IStatusResp {
  job_id: string;
  status: JobStatus;
  progress?: string;
  step?: string;
  error?: string;
}

export interface IReviewResp {
  job_id: string;
}
