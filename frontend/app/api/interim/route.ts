const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// GET /api/interim — list all job IDs that have interim files
export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/interim`, { cache: "no-store" })
    if (!res.ok) return Response.json({ jobs: [] })
    return Response.json(await res.json())
  } catch {
    return Response.json({ jobs: [] })
  }
}
