import type { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// GET /api/report/{jobId} — proxy to FastAPI JSON report endpoint
export async function GET(_req: NextRequest, ctx: RouteContext<"/api/report/[jobId]">) {
  const { jobId } = await ctx.params;

  const response = await fetch(`${BACKEND}/report/${jobId}`);
  const data = await response.json();

  return Response.json(data, { status: response.status });
}
