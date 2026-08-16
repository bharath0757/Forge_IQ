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

    const headers = [
      "part_number",
      "brand",
      "description",
      "category",
      "attribute_name",
      "raw_value",
      "canonical_value",
      "unit",
      "confidence_pct",
      "confidence_band",
      "status",
      "sources_count",
      "is_human_reviewed",
      "has_open_conflict",
    ];

    const rows = product.attributes.map((a) => [
      `"${product.part_number}"`,
      `"${product.brand}"`,
      `"${product.description}"`,
      `"${product.category}"`,
      `"${a.name}"`,
      `"${String(a.value ?? "")}"`,
      `"${String(a.normalized_value ?? a.value ?? "")}"`,
      `"${a.unit || ""}"`,
      a.confidence ? Math.round(a.confidence * 100) : 0,
      `"${a.confidence_breakdown?.confidence_band || (a.confidence >= 0.9 ? "HIGH" : a.confidence >= 0.7 ? "MEDIUM" : "LOW")}"`,
      `"${a.status}"`,
      a.evidence ? a.evidence.length : 0,
      a.is_human_reviewed ? "YES" : "NO",
      a.has_open_conflict ? "YES" : "NO",
    ]);

    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const filename = `${product.part_number.replace(/[^a-zA-Z0-9_-]/g, "_")}_twin.csv`;

    return new NextResponse(csvContent, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    });
  } catch (error) {
    return NextResponse.json({ detail: "CSV export failed" }, { status: 500 });
  }
}
