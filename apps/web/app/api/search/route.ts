export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const upstream = process.env.API_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${upstream}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: await request.text(),
      cache: "no-store",
    });
    return new Response(response.body, { status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json", "Cache-Control": "no-cache", "X-Accel-Buffering": "no" } });
  } catch {
    return Response.json({ detail: "The search API is unavailable." }, { status: 503 });
  }
}
