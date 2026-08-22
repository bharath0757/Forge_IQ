/**
 * ForgeIQ API Types
 * All TypeScript interfaces derived from the backend canonical schemas.
 * These are the ONLY types used to represent backend data in the frontend.
 */

// ── Evidence ────────────────────────────────────────────────────────────────

export interface EvidenceItem {
  id: string;
  document_name?: string;
  source_name?: string;
  page_number?: number;
  snippet: string;
  reliability_score?: number;
  similarity_score?: number;
}

// ── Confidence ──────────────────────────────────────────────────────────────

export type ConfidenceBand = "HIGH" | "MEDIUM" | "LOW";

export interface ConfidenceBreakdown {
  confidence_score: number;
  confidence_band: ConfidenceBand;
  source_reliability: number;
  evidence_strength: number;
  agreement_score: number;
  extraction_quality: number;
  validation_factor: number;
  conflict_factor: number;
  is_blocked_by_conflict?: boolean;
  explanation?: string;
}

// ── Attributes ──────────────────────────────────────────────────────────────

export interface ProductAttribute {
  id: string;
  name: string;
  value: string | number | null;
  normalized_value?: string | number | null;
  unit?: string;
  confidence: number;
  status: string;
  evidence: EvidenceItem[];
  evidence_ids: string[];
  confidence_breakdown?: ConfidenceBreakdown;
  is_human_reviewed?: boolean;
  has_open_conflict?: boolean;
}

// ── Conflicts ───────────────────────────────────────────────────────────────

export interface ConflictItem {
  id: string;
  attribute: string;
  values: (string | number | null)[];
  sources?: string[];
  severity: string;
  status: string;
}

// ── Review Decisions ────────────────────────────────────────────────────────

export interface ReviewDecisionItem {
  id: string;
  attribute: string;
  previous_value: string | number | null;
  selected_value: string | number | null;
  reviewer_action: string;
  reason: string;
  timestamp: string;
}

// ── Product Twin ────────────────────────────────────────────────────────────

export interface ProductTwinData {
  id: string;
  part_number: string;
  brand: string;
  description: string;
  category: string;
  overall_quality_score: number;
  status: string;
  evidence_count: number;
  attributes_count?: number;
  conflicts_count?: number;
  has_open_conflict?: boolean;
  attributes: ProductAttribute[];
  conflicts: ConflictItem[];
  review_decisions?: ReviewDecisionItem[];
  created_at: string;
  updated_at: string;
}

// ── Catalog Summary ─────────────────────────────────────────────────────────

export interface CatalogSummary {
  total_products: number;
  verified_count: number;
  needs_review_count: number;
  conflicts_count: number;
  average_quality_score: number;
}

// ── Pipeline Job ────────────────────────────────────────────────────────────

export type JobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface PipelineStageInfo {
  status: string;
  message?: string;
}

export interface PipelineJobData {
  job_id?: string;
  product_id?: string;
  status: JobStatus;
  stage: string;
  progress: number;
  stages: Record<string, PipelineStageInfo>;
  messages: string[];
}

// ── Delivery Validation ─────────────────────────────────────────────────────

export interface DeliveryValidationResult {
  status: string;
  processed: number;
  ready: number;
  review_required: number;
  critical_conflicts: number;
  evidence_coverage: number;
  overall_quality: number;
  schema_compliance: string;
}

// ── Batch Processing ────────────────────────────────────────────────────────

export interface BatchUploadResult {
  job_id: string;
  total_rows: number;
  status: string;
}

export interface BatchStatusResult {
  job_id: string;
  status: string;
  total: number;
  processed: number;
  succeeded: number;
  failed: number;
  errors: string[];
  product_ids: string[];
}

// ── Review Payload ──────────────────────────────────────────────────────────

export type ReviewAction =
  | "ACCEPT_AI_VALUE"
  | "SELECT_ALTERNATIVE"
  | "MARK_UNKNOWN"
  | "DISMISS_CONFLICT";

export interface ReviewPayload {
  attribute_name: string;
  action: ReviewAction;
  selected_value?: string | number | null;
  reason: string;
  reviewer: string;
}

// ── Export ───────────────────────────────────────────────────────────────────

export interface ExportJsonResult {
  product: Record<string, string | number | null>;
  attributes: Record<string, string | number | null>;
  evidence: Record<string, string | number | null>[];
  audit: Record<string, string | number | null>;
  delivery: Record<string, string | number | null>;
}

// ── API Error ───────────────────────────────────────────────────────────────

export interface ApiErrorResponse {
  detail: string;
}
