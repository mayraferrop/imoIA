import { NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

// Chamado pelo Vercel Cron a cada 14 minutos para manter o Render acordado
export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      signal: AbortSignal.timeout(30000),
    });
    const ok = res.ok;
    return NextResponse.json({
      status: ok ? "ok" : "error",
      render_status: res.status,
      timestamp: new Date().toISOString(),
    });
  } catch (e) {
    return NextResponse.json({
      status: "error",
      error: String(e),
      timestamp: new Date().toISOString(),
    });
  }
}
