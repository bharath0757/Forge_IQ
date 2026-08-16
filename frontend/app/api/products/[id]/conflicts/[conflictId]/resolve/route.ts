import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; conflictId: string }> }
) {
  try {
    const { id, conflictId } = await params;
    const body = await request.json();
    const { selected_value, reason } = body;

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
      "SELECT_ALTERNATIVE",
      selected_value,
      reason
    );

    return NextResponse.json({
      status: "SUCCESS",
      conflict_id: conflictId,
      conflict_status: "RESOLVED",
      message: `Conflict for '${conf.attribute}' successfully resolved with value '${selected_value}'.`,
    });
  } catch (error) {
    return NextResponse.json({ detail: "Failed to resolve conflict" }, { status: 500 });
  }
}
