import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const q = searchParams.get("q") || undefined;
    const status = searchParams.get("status") || undefined;
    const category = searchParams.get("category") || undefined;

    const list = engineStore.listProducts(q, status, category);
    return NextResponse.json(list);
  } catch (error) {
    return NextResponse.json({ detail: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const partNumber = formData.get("part_number") as string;
    const brand = formData.get("brand") as string;
    const description = formData.get("description") as string;
    const category = (formData.get("category") as string) || "General";
    const file = formData.get("file") as File | null;

    if (!partNumber || !partNumber.trim()) {
      return NextResponse.json({ detail: "Part number is required" }, { status: 422 });
    }
    if (!brand || !brand.trim()) {
      return NextResponse.json({ detail: "Brand is required" }, { status: 422 });
    }
    if (!description || !description.trim()) {
      return NextResponse.json({ detail: "Description is required" }, { status: 422 });
    }

    const created = engineStore.createProduct(partNumber, brand, description, category);

    return NextResponse.json({
      id: created.id,
      part_number: created.part_number,
      brand: created.brand,
      description: created.description,
      category: created.category,
      overall_quality_score: created.overall_quality_score,
      status: created.status,
      evidence_count: file ? 1 : 0,
      created_at: created.created_at,
      updated_at: created.updated_at,
      file_info: file ? { filename: file.name, size: file.size, content_type: file.type } : null,
      message: "Product ingested successfully. Ready for AI enrichment.",
    });
  } catch (error) {
    return NextResponse.json({ detail: "Failed to ingest product" }, { status: 500 });
  }
}
