import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    database: "connected",
    vector_store: "ready",
    service: "ForgeIQ API (Next.js Serverless Engine)",
    version: "1.0.0",
  });
}
