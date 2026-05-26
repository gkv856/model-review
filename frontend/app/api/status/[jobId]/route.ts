import type { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// GET /api/status/{jobId} — proxy to FastAPI job status endpoint
export async function GET(_req: NextRequest, ctx: RouteContext<"/api/status/[jobId]">) {
  const { jobId } = await ctx.params;

  const response = await fetch(`${BACKEND}/status/${jobId}`);
  const data = await response.json();

  return Response.json(data, { status: response.status });
}
