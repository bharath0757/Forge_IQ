import { NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function GET() {
  try {
    const summary = engineStore.getSummary();
    return NextResponse.json(summary);
  } catch (error) {
    return NextResponse.json({ detail: "Failed to load summary" }, { status: 500 });
  }
}
