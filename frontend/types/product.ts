export enum EntityStatus {
  DRAFT = "DRAFT",
  PROCESSING = "PROCESSING",
  REQUIRES_REVIEW = "REQUIRES_REVIEW",
  REVIEWED = "REVIEWED",
  PUBLISHED = "PUBLISHED",
}

export enum AttributeStatus {
  UNVERIFIED = "UNVERIFIED",
  VERIFIED = "VERIFIED",
  CONFLICT = "CONFLICT",
  UNKNOWN = "UNKNOWN",
}

export enum SeverityLevel {
  LOW = "LOW",
  MEDIUM = "MEDIUM",
  HIGH = "HIGH",
  CRITICAL = "CRITICAL",
}

export enum SourceType {
  PDF = "PDF",
  WEBSITE = "WEBSITE",
  IMAGE = "IMAGE",
  CATALOG = "CATALOG",
  API = "API",
}

export enum ReviewAction {
  APPROVE = "APPROVE",
  REJECT = "REJECT",
  MODIFY = "MODIFY",
}

export interface Source {
  id: string;
  name: string;
  type: SourceType;
  url?: string | null;
  document_name?: string | null;
}

export interface Evidence {
  id: string;
  source_name: string;
  source_type: SourceType;
  source_url?: string | null;
  document_name?: string | null;
  page_number?: number | null;
  snippet: string;
  extracted_text: string;
  reliability_score: number;
}

export interface ValidationResult {
  rule: string;
  passed: boolean;
  message: string;
  severity: SeverityLevel;
}

export interface Conflict {
  id: string;
  attribute: string;
  values: unknown[];
  sources: string[];
  severity: SeverityLevel;
  status: string;
}

export interface ReviewDecision {
  id: string;
  attribute: string;
  previous_value: unknown;
  selected_value: unknown;
  reviewer_action: ReviewAction;
  reason: string;
  timestamp: string; // ISO datetime string
}

export interface ProductAttribute {
  name: string;
  value: unknown;
  normalized_value?: unknown | null;
  unit?: string | null;
  confidence: number;
  status: AttributeStatus;
  evidence_ids: string[];
  conflict_ids: string[];
}

export interface Product {
  id: string;
  part_number: string;
  brand: string;
  description: string;
  category: string;
  attributes: ProductAttribute[];
  overall_quality_score: number;
  status: EntityStatus;
  evidence_count: number;
  conflicts: Conflict[];
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

export interface ProcessingJob {
  id: string;
  product_id: string;
  status: string;
  progress: number;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}
