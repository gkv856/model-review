"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, ArrowLeft, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
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

interface IInterimFile {
  name: string;
  size_bytes: number;
}

// Download helper — triggers browser file download from a URL
const downloadUrl = (url: string, filename: string) => {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
};

// Download helper — triggers browser file download from a string blob
const downloadBlob = (content: string, filename: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  downloadUrl(url, filename);
  URL.revokeObjectURL(url);
};

const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

  const [interimFiles, setInterimFiles] = useState<IInterimFile[]>([]);
  const [interimOpen, setInterimOpen] = useState(false);

  // Fetch interim file list once job completes
  useEffect(() => {
    if (!isCompleted) return;
    fetch(`/api/interim/${jobId}`)
      .then((r) => r.json())
      .then((data) => setInterimFiles(data.files ?? []))
      .catch(() => {});
  }, [isCompleted, jobId]);

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
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Review another model
          </button>

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
                      <p className="font-medium text-[var(--sev-critical-fg)] mb-1">Circular references</p>
                      <div className="flex flex-wrap gap-1">
                        {report.graph_analysis.circular_references.map((ref) => (
                          <span key={ref} className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">{ref}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {report.graph_analysis.broken_references.length > 0 && (
                    <div>
                      <p className="font-medium text-[var(--sev-critical-fg)] mb-1">Broken references</p>
                      <div className="flex flex-wrap gap-1">
                        {report.graph_analysis.broken_references.map((ref) => (
                          <span key={ref} className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">{ref}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {report.graph_analysis.external_links_in_chain.length > 0 && (
                    <div>
                      <p className="font-medium text-[var(--sev-warning-fg)] mb-1">External links in dependency chain</p>
                      <div className="flex flex-wrap gap-1">
                        {report.graph_analysis.external_links_in_chain.map((ref) => (
                          <span key={ref} className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">{ref}</span>
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

            {/* Interim stage files */}
            {interimFiles.length > 0 && (
              <Card>
                <CardHeader className="cursor-pointer select-none" onClick={() => setInterimOpen((o) => !o)}>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                      Pipeline Stage Files ({interimFiles.length})
                    </CardTitle>
                    {interimOpen
                      ? <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      : <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    }
                  </div>
                  {!interimOpen && (
                    <p className="text-xs text-muted-foreground mt-1">
                      CSV and JSON outputs from each pipeline step — click to expand
                    </p>
                  )}
                </CardHeader>
                {interimOpen && (
                  <CardContent>
                    <div className="flex flex-col divide-y divide-border">
                      {interimFiles.map((file) => (
                        <div key={file.name} className="flex items-center justify-between py-2.5 gap-4">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="font-mono text-xs text-foreground truncate">{file.name}</span>
                            <span className="text-xs text-muted-foreground shrink-0">{formatBytes(file.size_bytes)}</span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs shrink-0"
                            onClick={() => downloadUrl(`/api/interim/${jobId}/${file.name}`, file.name)}
                          >
                            <Download className="w-3 h-3 mr-1" />
                            Download
                          </Button>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                )}
              </Card>
            )}
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
