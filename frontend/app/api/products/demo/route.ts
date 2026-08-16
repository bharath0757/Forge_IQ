import { NextResponse } from "next/server";
import { engineStore } from "@/lib/store";

export async function POST() {
  try {
    const { product, job } = engineStore.runDemoPipeline();
    return NextResponse.json({
      status: "SUCCESS",
      product_id: product.id,
      job_id: job.job_id,
      quality_score: product.overall_quality_score,
      product_status: product.status,
      message: "Siemens 3RV2011 demo pipeline executed successfully across all 8 stages.",
    });
  } catch (error) {
    return NextResponse.json({ detail: "Demo launch failed" }, { status: 500 });
  }
}
