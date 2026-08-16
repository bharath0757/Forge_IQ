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

    const payload = {
      forge_iq_version: "1.0",
      exported_at: new Date().toISOString(),
      product: {
        id: product.id,
        part_number: product.part_number,
        brand: product.brand,
        description: product.description,
        category: product.category,
        overall_quality_score: product.overall_quality_score,
        status: product.status,
        evidence_count: product.evidence_count,
        created_at: product.created_at,
        updated_at: product.updated_at,
      },
      product_twin: {
        ...product,
        audit_trail: product.review_decisions || [],
      },
      attributes: product.attributes,
      conflicts: product.conflicts,
      review_history: product.review_decisions || [],
    };

    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json({ detail: "Export failed" }, { status: 500 });
  }
}
