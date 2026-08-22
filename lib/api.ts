/**
 * ForgeIQ Unified API Client
 * Single source of truth for all backend communication.
 * No fetch() calls should exist outside this module.
 */

import type {
  ProductTwinData,
  CatalogSummary,
  PipelineJobData,
  DeliveryValidationResult,
  BatchUploadResult,
  BatchStatusResult,
  ReviewPayload,
  ExportJsonResult,
  ApiErrorResponse,
} from "@/types/api";

const API_BASE = "";

// ── Error Handling ──────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getUserFacingMessage(status: number, detail: string): string {
  switch (status) {
    case 400:
      return `Invalid request: ${detail}`;
    case 401:
      return "Authentication required. Please log in.";
    case 403:
      return "You do not have permission to perform this action.";
    case 404:
      return `Resource not found: ${detail}`;
    case 409:
      return `Conflict: ${detail}`;
    case 422:
      return `Validation error: ${detail}`;
    case 429:
      return "Too many requests. Please wait and try again.";
    case 500:
      return "An internal server error occurred. Please try again later.";
    default:
      return detail || `Unexpected error (HTTP ${status})`;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errBody: ApiErrorResponse = await res.json();
      detail = errBody.detail || detail;
    } catch {
      // Response body wasn't JSON
    }
    throw new ApiError(res.status, getUserFacingMessage(res.status, detail));
  }
  return res.json() as Promise<T>;
}

// ── Products ────────────────────────────────────────────────────────────────

export async function getProducts(): Promise<ProductTwinData[]> {
  const res = await fetch(`${API_BASE}/api/products`);
  return handleResponse<ProductTwinData[]>(res);
}

export async function getProduct(id: string): Promise<ProductTwinData> {
  const res = await fetch(`${API_BASE}/api/products/${id}`);
  return handleResponse<ProductTwinData>(res);
}

export async function getProductSummary(): Promise<CatalogSummary> {
  const res = await fetch(`${API_BASE}/api/products/summary`);
  return handleResponse<CatalogSummary>(res);
}

export async function ingestProduct(
  partNumber: string,
  brand: string,
  description: string,
  file?: File | null
): Promise<ProductTwinData> {
  const formData = new FormData();
  formData.append("part_number", partNumber);
  formData.append("brand", brand);
  formData.append("description", description);
  if (file) formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/products`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<ProductTwinData>(res);
}

// ── Pipeline ────────────────────────────────────────────────────────────────

export async function getJobStatus(productId: string): Promise<PipelineJobData> {
  const res = await fetch(`${API_BASE}/api/products/${productId}/job`);
  return handleResponse<PipelineJobData>(res);
}

export async function runDemoPipeline(productId?: string): Promise<{ product_id: string }> {
  const url = productId
    ? `${API_BASE}/api/products/demo?product_id=${productId}`
    : `${API_BASE}/api/products/demo`;
  const res = await fetch(url, { method: "POST" });
  return handleResponse<{ product_id: string }>(res);
}

export async function seedDemoProducts(): Promise<{ seeded: number }> {
  const res = await fetch(`${API_BASE}/api/products/demo/seed`, { method: "POST" });
  return handleResponse<{ seeded: number }>(res);
}

// ── Review ──────────────────────────────────────────────────────────────────

export async function submitReview(
  productId: string,
  payload: ReviewPayload
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/products/${productId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<Record<string, unknown>>(res);
}

export async function approveProduct(
  productId: string
): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/products/${productId}/approve`, {
    method: "POST",
  });
  return handleResponse<Record<string, unknown>>(res);
}

// ── Export ───────────────────────────────────────────────────────────────────

export async function exportProductJson(
  productId: string
): Promise<ExportJsonResult> {
  const res = await fetch(`${API_BASE}/api/products/${productId}/export/json`);
  return handleResponse<ExportJsonResult>(res);
}

export function getExportCsvUrl(productId: string): string {
  return `${API_BASE}/api/products/${productId}/export/csv`;
}

// ── Delivery ────────────────────────────────────────────────────────────────

export async function validateDelivery(): Promise<DeliveryValidationResult> {
  const res = await fetch(`${API_BASE}/api/delivery/validate`);
  return handleResponse<DeliveryValidationResult>(res);
}

export async function getOperationalMetrics(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/delivery/metrics`);
  return handleResponse<Record<string, unknown>>(res);
}

export function getDeliveryExportUrl(): string {
  return `${API_BASE}/api/delivery/export`;
}

export function getEvaluatedDeliveryExportUrl(): string {
  return `${API_BASE}/api/delivery/export?source=evaluated`;
}

// ── Batch ───────────────────────────────────────────────────────────────────

export async function uploadBatch(file: File): Promise<BatchUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/batch/upload`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<BatchUploadResult>(res);
}

export async function getBatchStatus(jobId: string): Promise<BatchStatusResult> {
  const res = await fetch(`${API_BASE}/api/batch/${jobId}/status`);
  return handleResponse<BatchStatusResult>(res);
}

export async function processBatchChunk(
  jobId: string
): Promise<BatchStatusResult> {
  const res = await fetch(`${API_BASE}/api/batch/${jobId}/process_chunk`, {
    method: "POST",
  });
  return handleResponse<BatchStatusResult>(res);
}
