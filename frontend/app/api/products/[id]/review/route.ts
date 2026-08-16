import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const { attribute_name, action, selected_value, reason, reviewer } = body;

    if (!attribute_name || !action) {
      return NextResponse.json(
        { detail: "attribute_name and action are required" },
        { status: 400 }
      );
    }

    const updated = engineStore.reviewAttribute(
      id,
      attribute_name,
      action,
      selected_value,
      reason
    );

    if (!updated) {
      return NextResponse.json({ detail: "Product not found" }, { status: 404 });
    }

    return NextResponse.json({
      status: "SUCCESS",
      action,
      attribute_name,
      selected_value,
      quality_score: updated.overall_quality_score,
      product_status: updated.status,
      decision_id: `dec_${Math.random().toString(36).substring(2, 10)}`,
    });
  } catch (error) {
    return NextResponse.json({ detail: "Failed to submit review" }, { status: 500 });
  }
}
