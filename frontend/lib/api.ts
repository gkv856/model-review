import type { IReport, IReviewResp, IStatusResp } from "@/lib/types";

interface IApiConfig {
  baseUrl: string;
  streaming: boolean;
}

interface ISubmitReview {
  modelFile: File;
  mapFile: File;
}

interface IJobId {
  jobId: string;
}

// Wraps all backend API calls
// streaming flag: when true, uses EventSource (SSE) for status updates
class ModelReviewApi {
  private baseUrl: string;
  private streaming: boolean;

  constructor(props: IApiConfig) {
    const { baseUrl, streaming } = props;
    this.baseUrl = baseUrl;
    this.streaming = streaming;
  }

  // Input: modelFile, mapFile
  // Output: IReviewResp with job_id
  async submitReview(props: ISubmitReview): Promise<IReviewResp> {
    const { modelFile, mapFile } = props;

    const formData = new FormData();
    formData.append("model_file", modelFile);
    formData.append("map_file", mapFile);

    const response = await fetch(`${this.baseUrl}/review`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Submit failed: ${response.status} — ${text}`);
    }

    return response.json() as Promise<IReviewResp>;
  }

  // Input: jobId
  // Output: IStatusResp with status, progress, step
  async getStatus(props: IJobId): Promise<IStatusResp> {
    const { jobId } = props;

    const response = await fetch(`${this.baseUrl}/status/${jobId}`);

    if (!response.ok) {
      throw new Error(`Status check failed: ${response.status}`);
    }

    return response.json() as Promise<IStatusResp>;
  }

  // Input: jobId
  // Output: full IReport JSON
  async getReport(props: IJobId): Promise<IReport> {
    const { jobId } = props;

    const response = await fetch(`${this.baseUrl}/report/${jobId}`);

    if (!response.ok) {
      throw new Error(`Report fetch failed: ${response.status}`);
    }

    return response.json() as Promise<IReport>;
  }

  // Input: jobId
  // Output: standalone HTML string for download
  async getReportHtml(props: IJobId): Promise<string> {
    const { jobId } = props;

    const response = await fetch(`${this.baseUrl}/report/${jobId}/html`);

    if (!response.ok) {
      throw new Error(`HTML report fetch failed: ${response.status}`);
    }

    return response.text();
  }

  // Input: jobId, onMessage callback
  // Output: EventSource subscription (call .close() to stop)
  // Only active when streaming = true
  streamStatus(props: IJobId & { onMessage: (data: IStatusResp) => void }): EventSource | null {
    if (!this.streaming) return null;

    const { jobId, onMessage } = props;
    const source = new EventSource(`${this.baseUrl}/status/${jobId}/stream`);

    source.onmessage = (event) => {
      const data = JSON.parse(event.data) as IStatusResp;
      onMessage(data);
    };

    return source;
  }
}

// Singleton — proxied through Next.js API routes to avoid CORS
export const api = new ModelReviewApi({
  baseUrl: "/api",
  streaming: false,
});
