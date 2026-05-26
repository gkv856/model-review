import type { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// GET /api/interim/{jobId} — list available interim stage files
export async function GET(_req: NextRequest, ctx: RouteContext<"/api/interim/[jobId]">) {
  const { jobId } = await ctx.params;

  const response = await fetch(`${BACKEND}/interim/${jobId}`);
  const data = await response.json();

  return Response.json(data, { status: response.status });
}
