"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { Download, ArrowLeft, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import SummaryCard from "@/components/SummaryCard";
import IssuesTable from "@/components/IssuesTable";
import ProgressIndicator from "@/components/ProgressIndicator";
import { useJobStatus } from "@/hooks/useJobStatus";
import { useReport } from "@/hooks/useReport";
import { api } from "@/lib/api";

interface IPageProps {
  params: Promise<{ jobId: string }>;
}

// Download helper — triggers browser file download from a string blob
const downloadBlob = (content: string, filename: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

// Results page — polls for job status, then shows report once complete
export default function ResultsPage(props: IPageProps) {
  const { params } = props;
  const { jobId } = use(params);
  const router = useRouter();

  const statusQuery = useJobStatus({ jobId });
  const status = statusQuery.data;

  const isCompleted = status?.status === "completed";
  const isFailed = status?.status === "failed";

  const reportQuery = useReport({ jobId, enabled: isCompleted });
  const report = reportQuery.data;

  const handleDownloadJson = async () => {
    const data = await api.getReport({ jobId });
    downloadBlob(JSON.stringify(data, null, 2), `review-${jobId}.json`, "application/json");
  };

  const handleDownloadHtml = async () => {
    const html = await api.getReportHtml({ jobId });
    downloadBlob(html, `review-${jobId}.html`, "text/html");
  };

  return (
    <main className="min-h-screen px-4 py-10">
      <div className="max-w-7xl mx-auto flex flex-col gap-8">

        {/* Top bar */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/")}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Review another model
            </button>
          </div>

          {isCompleted && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleDownloadJson}>
                <Download className="w-3.5 h-3.5 mr-1.5" />
                JSON Report
              </Button>
              <Button variant="outline" size="sm" onClick={handleDownloadHtml}>
                <Download className="w-3.5 h-3.5 mr-1.5" />
                HTML Report
              </Button>
            </div>
          )}
        </div>

        {/* Page title */}
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Job {jobId}
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {isCompleted ? "Review Complete" : isFailed ? "Review Failed" : "Analysis in Progress"}
          </h1>
        </div>

        {/* Progress — shown while not yet complete */}
        {!isCompleted && !isFailed && status && (
          <Card>
            <CardContent className="pt-6">
              <ProgressIndicator status={status} />
            </CardContent>
          </Card>
        )}

        {/* Error state */}
        {isFailed && (
          <Card className="border-[var(--sev-critical-border)]">
            <CardContent className="pt-6 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[var(--sev-critical-fg)] shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-foreground">Analysis failed</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {status?.error ?? "An unexpected error occurred. Please try again."}
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Report — shown once complete */}
        {isCompleted && report && (
          <>
            {/* Summary */}
            <SummaryCard report={report} />

            {/* Graph analysis — shown only when issues exist */}
            {(report.graph_analysis.circular_references.length > 0 ||
              report.graph_analysis.broken_references.length > 0 ||
              report.graph_analysis.external_links_in_chain.length > 0) && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                    Graph Analysis Flags
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 text-sm">
                  {report.graph_analysis.circular_references.length > 0 && (
                    <div>
                      <p className="font-medium text-[var(--sev-critical-fg)] mb-1">
                        Circular references
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {report.graph_analysis.circular_references.map((ref) => (
                          <span key={ref} className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                            {ref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {report.graph_analysis.broken_references.length > 0 && (
                    <div>
                      <p className="font-medium text-[var(--sev-critical-fg)] mb-1">
                        Broken references
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {report.graph_analysis.broken_references.map((ref) => (
                          <span key={ref} className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                            {ref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {report.graph_analysis.external_links_in_chain.length > 0 && (
                    <div>
                      <p className="font-medium text-[var(--sev-warning-fg)] mb-1">
                        External links in dependency chain
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {report.graph_analysis.external_links_in_chain.map((ref) => (
                          <span key={ref} className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                            {ref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Issues table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Issues ({report.issues.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <IssuesTable issues={report.issues} />
              </CardContent>
            </Card>
          </>
        )}

        {/* Loading state while report fetches after completion */}
        {isCompleted && reportQuery.isLoading && (
          <p className="text-sm text-muted-foreground text-center">Loading report...</p>
        )}

      </div>
    </main>
  );
}
