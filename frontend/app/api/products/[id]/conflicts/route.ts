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
    return NextResponse.json(product.conflicts || []);
  } catch (error) {
    return NextResponse.json({ detail: "Failed to load conflicts" }, { status: 500 });
  }
}
