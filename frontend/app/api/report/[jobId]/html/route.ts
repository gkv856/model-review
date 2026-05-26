import type { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// GET /api/report/{jobId}/html — proxy to FastAPI HTML report endpoint
export async function GET(_req: NextRequest, ctx: RouteContext<"/api/report/[jobId]/html">) {
  const { jobId } = await ctx.params;

  const response = await fetch(`${BACKEND}/report/${jobId}/html`);
  const html = await response.text();

  return new Response(html, {
    status: response.status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}
