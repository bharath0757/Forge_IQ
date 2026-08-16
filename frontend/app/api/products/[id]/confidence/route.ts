import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const product = engineStore.getProductById(id);
    if (!product) {
      return NextResponse.json({ detail: "Product not found" }, { status: 404 });
    }

    const breakdowns = product.attributes.map((a) => a.confidence_breakdown).filter(Boolean);

    return NextResponse.json({
      product_id: id,
      overall_quality_score: product.overall_quality_score,
      attribute_breakdowns: breakdowns,
    });
  } catch (error) {
    return NextResponse.json({ detail: "Failed to load confidence" }, { status: 500 });
  }
}
