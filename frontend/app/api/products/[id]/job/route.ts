import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const job = engineStore.getJob(id);
    return NextResponse.json(job);
  } catch (error) {
    return NextResponse.json({ detail: "Failed to get job" }, { status: 500 });
  }
}
