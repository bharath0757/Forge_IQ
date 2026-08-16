import { NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function POST() {
  try {
    engineStore.seedDefaults();
    const products = engineStore.listProducts();
    return NextResponse.json({
      status: "SUCCESS",
      seeded_count: products.length,
      products: products.map((p) => ({
        id: p.id,
        part_number: p.part_number,
        brand: p.brand,
        category: p.category,
        quality_score: p.overall_quality_score,
        status: p.status,
      })),
      message: `Successfully seeded ${products.length} realistic industrial demo products.`,
    });
  } catch (error) {
    return NextResponse.json({ detail: "Demo seed failed" }, { status: 500 });
  }
}
