import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; conflictId: string }> }
) {
  try {
    const { id, conflictId } = await params;
    const body = await request.json().catch(() => ({}));
    const { reason } = body;

    const product = engineStore.getProductById(id);
    if (!product) {
      return NextResponse.json({ detail: "Product not found" }, { status: 404 });
    }

    const conf = product.conflicts?.find((c) => c.id === conflictId);
    if (!conf) {
      return NextResponse.json({ detail: "Conflict not found" }, { status: 404 });
    }

    engineStore.reviewAttribute(
      id,
      conf.attribute,
      "DISMISS_CONFLICT",
      undefined,
      reason || "Dismissed by reviewer"
    );

    return NextResponse.json({
      status: "SUCCESS",
      conflict_id: conflictId,
      conflict_status: "DISMISSED",
      message: `Conflict for '${conf.attribute}' dismissed.`,
    });
  } catch (error) {
    return NextResponse.json({ detail: "Failed to dismiss conflict" }, { status: 500 });
  }
}
