"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { History, ChevronRight, FileText } from "lucide-react";
import DualFileUpload from "@/components/DualFileUpload";
import { useReview } from "@/hooks/useReview";

interface IPastRun {
  job_id: string
  file_count: number
  model_filename: string | null
  started_at: string | null
}

// Upload page — entry point for model + map file submission
export default function UploadPage() {
  const { mutateAsync, isPending, error } = useReview();
  const router = useRouter();

  const [pastRuns, setPastRuns] = useState<IPastRun[]>([]);

  useEffect(() => {
    fetch("/api/interim")
      .then((r) => r.json())
      .then((data) => setPastRuns(data.jobs ?? []))
      .catch(() => {});
  }, []);

  const handleSubmit = async (modelFile: File, mapFile: File) => {
    await mutateAsync({ modelFile, mapFile });
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-2xl flex flex-col gap-8">

        {/* Header */}
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Financial Model Review
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Model Integrity Reviewer
          </h1>
          <p className="text-sm text-muted-foreground max-w-lg">
            Upload your Excel model and the VBA-generated map file. The pipeline
            analyses unique formulas only — graph-first, LLM-last.
          </p>
        </div>

        {/* Upload form */}
        <div className="rounded-xl border border-border bg-card p-6">
          <DualFileUpload onSubmit={handleSubmit} isLoading={isPending} />
        </div>

        {/* Error state */}
        {error && (
          <p className="text-sm text-[var(--sev-critical-fg)] text-center">
            {error instanceof Error ? error.message : "Submission failed. Please try again."}
          </p>
        )}

        {/* Past runs */}
        {pastRuns.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <History className="w-3.5 h-3.5 text-muted-foreground" />
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Previous Runs
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-[#13161f] overflow-hidden divide-y divide-white/[0.05]">
              {pastRuns.map((run) => (
                <button
                  key={run.job_id}
                  onClick={() => router.push(`/results/${run.job_id}/pipeline`)}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.04] transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-7 h-7 rounded-md bg-white/5 flex items-center justify-center shrink-0">
                      <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-foreground/90 truncate">
                        {run.model_filename ?? "Unknown model"}
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-2">
                        <span className="font-mono">{run.job_id.slice(0, 8)}…</span>
                        <span>·</span>
                        <span>{run.file_count} of 12 stages</span>
                        {run.started_at && (
                          <>
                            <span>·</span>
                            <span>{new Date(run.started_at).toLocaleDateString()}</span>
                          </>
                        )}
                      </p>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-white/50 transition-colors shrink-0 ml-3" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer note */}
        <p className="text-xs text-muted-foreground text-center">
          Both files must be .xlsx — max 150MB each. No data is stored beyond the current session.
        </p>

      </div>
    </main>
  );
}
