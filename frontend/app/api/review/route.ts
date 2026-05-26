import { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// POST /api/review — proxy multipart upload to FastAPI backend
export async function POST(req: NextRequest) {
  const formData = await req.formData();

  const response = await fetch(`${BACKEND}/review`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();

  return Response.json(data, { status: response.status });
}
