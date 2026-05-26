import type { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// GET /api/interim/{jobId}/{filename} — proxy file download from FastAPI
export async function GET(
  _req: NextRequest,
  ctx: RouteContext<"/api/interim/[jobId]/[filename]">
) {
  const { jobId, filename } = await ctx.params;

  const response = await fetch(`${BACKEND}/interim/${jobId}/${filename}`);

  if (!response.ok) {
    return new Response("File not found", { status: response.status });
  }

  const contentType = filename.endsWith(".json") ? "application/json" : "text/csv";

  return new Response(response.body, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
