import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const productId = formData.get("product_id") as string | null;

    if (!file) {
      return NextResponse.json({ detail: "No file provided" }, { status: 422 });
    }

    const docId = `doc_${Math.random().toString(36).substring(2, 10)}`;
    const pageCount = file.name.endsWith(".pdf") ? 4 : 1;

    return NextResponse.json({
      document_id: docId,
      filename: file.name,
      page_count: pageCount,
      extracted_text_count: 8,
      status: "COMPLETED",
      product_id: productId,
      error_message: null,
    });
  } catch (error) {
    return NextResponse.json({ detail: "Document upload failed" }, { status: 500 });
  }
}
