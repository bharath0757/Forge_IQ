import { NextRequest, NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const product = engineStore.getProductById(id);
    if (!product) {
      return NextResponse.json({ detail: "Product not found" }, { status: 404 });
    }

    const openCritical = product.conflicts.filter(
      (c) => c.status === "OPEN" && ["HIGH", "CRITICAL"].includes(c.severity)
    ).length;

    if (openCritical > 0) {
      return NextResponse.json(
        {
          detail: `Cannot approve product: ${openCritical} open high-severity conflict(s) must be reviewed first.`,
        },
        { status: 400 }
      );
    }

    const approved = engineStore.approveProduct(id);

    return NextResponse.json({
      status: "SUCCESS",
      product_id: id,
      product_status: approved?.status || "PUBLISHED",
      message: "Product Twin approved and published successfully.",
    });
  } catch (error) {
    return NextResponse.json({ detail: "Failed to approve product" }, { status: 500 });
  }
}
