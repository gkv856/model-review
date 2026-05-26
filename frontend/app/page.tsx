"use client";

import DualFileUpload from "@/components/DualFileUpload";
import { useReview } from "@/hooks/useReview";

// Upload page — entry point for model + map file submission
export default function UploadPage() {
  const { mutateAsync, isPending, error } = useReview();

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

        {/* Footer note */}
        <p className="text-xs text-muted-foreground text-center">
          Both files must be .xlsx — max 150MB each. No data is stored beyond the current session.
        </p>

      </div>
    </main>
  );
}
