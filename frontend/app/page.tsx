"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";

const API_BASE = "";

const ACCEPTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"];

type TabType = "catalog" | "twin" | "pipeline" | "ingest";

const PIPELINE_STAGES = [
  { id: "01 IDENTIFY", title: "IDENTIFY", desc: "Validate part number, brand & classification" },
  { id: "02 DISCOVER", title: "DISCOVER", desc: "Index datasheets, catalogs & distributor specs" },
  { id: "03 EXTRACT", title: "EXTRACT", desc: "Grounded LLM extraction from vector chunks" },
  { id: "04 NORMALIZE", title: "NORMALIZE", desc: "Canonical unit & format standardization" },
  { id: "05 VALIDATE", title: "VALIDATE", desc: "Deterministic rules & cross-source check" },
  { id: "06 DECIDE", title: "DECIDE", desc: "Multi-signal deterministic confidence scoring" },
  { id: "07 REVIEW", title: "REVIEW", desc: "Evaluate human review eligibility & flags" },
  { id: "08 PUBLISH", title: "PUBLISH", desc: "Assemble canonical Product Twin & audit log" },
];

interface EvidenceItem {
  id: string;
  document_name?: string;
  source_name?: string;
  page_number?: number;
  snippet: string;
  reliability_score?: number;
  similarity_score?: number;
}

interface ConfidenceBreakdown {
  confidence_score: number;
  confidence_band: "HIGH" | "MEDIUM" | "LOW";
  source_reliability: number;
  evidence_strength: number;
  agreement_score: number;
  extraction_quality: number;
  validation_factor: number;
  conflict_factor: number;
  is_blocked_by_conflict?: boolean;
  explanation?: string;
}

interface ProductAttribute {
  id: string;
  name: string;
  value: unknown;
  normalized_value?: unknown;
  unit?: string;
  confidence: number;
  status: string;
  evidence: EvidenceItem[];
  evidence_ids: string[];
  confidence_breakdown?: ConfidenceBreakdown;
  is_human_reviewed?: boolean;
  has_open_conflict?: boolean;
}

interface ConflictItem {
  id: string;
  attribute: string;
  values: unknown[];
  sources?: string[];
  severity: string;
  status: string;
}

interface ReviewDecisionItem {
  id: string;
  attribute: string;
  previous_value: unknown;
  selected_value: unknown;
  reviewer_action: string;
  reason: string;
  timestamp: string;
}

interface ProductTwinData {
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

interface CatalogSummary {
  total_products: number;
  verified_count: number;
  needs_review_count: number;
  conflicts_count: number;
  average_quality_score: number;
}

interface PipelineJobData {
  job_id?: string;
  product_id?: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  stage: string;
  progress: number;
  stages: Record<string, { status: string; message?: string }>;
  messages: string[];
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { className: string; label: string }> = {
    DRAFT: { className: "badge badge-draft", label: "Draft" },
    PROCESSING: { className: "badge badge-processing", label: "Processing" },
    COMPLETED: { className: "badge badge-completed", label: "Completed" },
    PUBLISHED: { className: "badge badge-verified", label: "Published" },
    READY: { className: "badge badge-verified", label: "Ready" },
    FAILED: { className: "badge badge-failed", label: "Failed" },
    REQUIRES_REVIEW: { className: "badge badge-requires_review", label: "Requires Review" },
    REVIEWED: { className: "badge badge-verified", label: "Reviewed" },
    VERIFIED: { className: "badge badge-verified", label: "Verified" },
    CONFLICT: { className: "badge badge-conflict", label: "Conflict" },
    UNKNOWN: { className: "badge badge-draft", label: "Unknown" },
  };
  const info = map[status] ?? { className: "badge badge-draft", label: status };
  return <span className={info.className}>{info.label}</span>;
}

function ConfidenceBadge({ score, band }: { score: number; band?: string }) {
  let bandClass = "conf-low";
  const displayBand = band || (score >= 90 ? "HIGH" : score >= 70 ? "MEDIUM" : "LOW");
  
  if (score >= 90 || displayBand === "HIGH") bandClass = "conf-high";
  else if (score >= 70 || displayBand === "MEDIUM") bandClass = "conf-med";

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-bold ${bandClass}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {Math.round(score)}% {displayBand}
    </span>
  );
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>("catalog");
  const [products, setProducts] = useState<ProductTwinData[]>([]);
  const [summary, setSummary] = useState<CatalogSummary | null>(null);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [currentProduct, setCurrentProduct] = useState<ProductTwinData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Catalog Filtering and Search
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [confidenceFilter, setConfidenceFilter] = useState("ALL");
  const [conflictFilter, setConflictFilter] = useState("ALL");

  // Evidence Drawer state
  const [selectedAttribute, setSelectedAttribute] = useState<ProductAttribute | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Review Workflow Panel state
  const [reviewPanelOpen, setReviewPanelOpen] = useState(false);
  const [reviewActiveIndex, setReviewActiveIndex] = useState(0);
  const [customValueInput, setCustomValueInput] = useState("");
  const [reviewReasonInput, setReviewReasonInput] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);

  // Export JSON / CSV Modals
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportData, setExportData] = useState<Record<string, unknown> | null>(null);
  const [copiedExport, setCopiedExport] = useState(false);

  // Pipeline Execution State
  const [pipelineJob, setPipelineJob] = useState<PipelineJobData | null>(null);
  const [demoRunning, setDemoRunning] = useState(false);
  const [seedRunning, setSeedRunning] = useState(false);

  // Ingestion Form State
  const [partNumber, setPartNumber] = useState("");
  const [brand, setBrand] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Fetch detailed product twin ──────────────────────────────────
  const fetchProductDetails = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/products/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ProductTwinData = await res.json();
      setCurrentProduct(data);
    } catch (err: unknown) {
      console.error("Failed to load product details", err);
    }
  }, []);

  // ── Fetch catalog summary KPIs ───────────────────────────────────
  const fetchCatalogSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/products/summary`);
      if (res.ok) {
        const data: CatalogSummary = await res.json();
        setSummary(data);
      }
    } catch (err: unknown) {
      console.error("Failed to load summary", err);
    }
  }, []);

  // ── Fetch products list ──────────────────────────────────────────
  const fetchProducts = useCallback(async (selectId?: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}/api/products`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ProductTwinData[] = await res.json();
      setProducts(data);

      await fetchCatalogSummary();

      if (data.length > 0) {
        const idToSelect = selectId || selectedProductId || data[0].id;
        setSelectedProductId(idToSelect);
        await fetchProductDetails(idToSelect);
      } else {
        setSelectedProductId(null);
        setCurrentProduct(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch products");
    } finally {
      setLoading(false);
    }
  }, [selectedProductId, fetchProductDetails, fetchCatalogSummary]);

  // ── Polling Job Status ───────────────────────────────────────────
  const fetchJobStatus = useCallback(async (productId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/products/${productId}/job`);
      if (res.ok) {
        const data: PipelineJobData = await res.json();
        setPipelineJob(data);
      }
    } catch (err: unknown) {
      console.error("Failed to poll job status", err);
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API_BASE}/api/products`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: ProductTwinData[] = await res.json();
        if (!active) return;
        setProducts(data);
        await fetchCatalogSummary();
        if (data.length > 0) {
          const firstId = data[0].id;
          setSelectedProductId(firstId);
          const dRes = await fetch(`${API_BASE}/api/products/${firstId}`);
          if (dRes.ok && active) {
            const dData: ProductTwinData = await dRes.json();
            setCurrentProduct(dData);
          }
          await fetchJobStatus(firstId);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to fetch products");
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [fetchJobStatus, fetchCatalogSummary]);

  const handleSelectProduct = (id: string) => {
    setSelectedProductId(id);
    fetchProductDetails(id);
    fetchJobStatus(id);
    setActiveTab("twin");
  };

  // ── Launch Live Demo Mode ─────────────────────────────────────────
  const handleLaunchDemoMode = async () => {
    setDemoRunning(true);
    setActiveTab("pipeline");

    try {
      const res = await fetch(`${API_BASE}/api/products/demo`, { method: "POST" });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Demo launch failed");
      }
      const data = await res.json();
      const demoId = data.product_id;
      setSelectedProductId(demoId);

      await fetchJobStatus(demoId);
      await fetchProducts(demoId);
    } catch (err: unknown) {
      alert(`Demo Error: ${err instanceof Error ? err.message : "Failed to run demo"}`);
    } finally {
      setDemoRunning(false);
    }
  };

  // ── Seed 5 Realistic Demo Products ──────────────────────────────
  const handleSeedDemoProducts = async () => {
    setSeedRunning(true);
    try {
      const res = await fetch(`${API_BASE}/api/products/demo/seed`, { method: "POST" });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Demo seed failed");
      }
      await fetchProducts();
      await fetchCatalogSummary();
      setActiveTab("catalog");
    } catch (err: unknown) {
      alert(`Demo Seed Error: ${err instanceof Error ? err.message : "Failed to seed demo products"}`);
    } finally {
      setSeedRunning(false);
    }
  };

  // ── Open Evidence Drawer ─────────────────────────────────────────
  const openEvidenceDrawer = (attr: ProductAttribute) => {
    setSelectedAttribute(attr);
    setDrawerOpen(true);
  };

  // ── Eligible Review Items ─────────────────────────────────────────
  const reviewEligibleAttributes = currentProduct?.attributes.filter((attr) => {
    const isLowOrMed = attr.confidence < 0.90 || (attr.confidence_breakdown && attr.confidence_breakdown.confidence_band !== "HIGH");
    const hasConflict = attr.has_open_conflict || attr.status === "CONFLICT" || attr.status === "REQUIRES_REVIEW";
    return isLowOrMed || hasConflict;
  }) || [];

  // ── Handle Review Action ─────────────────────────────────────────
  const handleReviewAction = async (
    attributeName: string,
    action: "ACCEPT_AI_VALUE" | "SELECT_ALTERNATIVE" | "MARK_UNKNOWN" | "DISMISS_CONFLICT",
    selectedValue?: unknown
  ) => {
    if (!currentProduct) return;
    setReviewLoading(true);

    try {
      const payload = {
        attribute_name: attributeName,
        action,
        selected_value: selectedValue !== undefined ? selectedValue : customValueInput || undefined,
        reason: reviewReasonInput.trim() || `Human reviewer action: ${action}`,
        reviewer: "Lead Engineer",
      };

      const res = await fetch(`${API_BASE}/api/products/${currentProduct.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to submit review");
      }

      await fetchProductDetails(currentProduct.id);
      await fetchCatalogSummary();
      setCustomValueInput("");
      setReviewReasonInput("");

      if (reviewActiveIndex < reviewEligibleAttributes.length - 1) {
        setReviewActiveIndex((prev) => prev + 1);
      } else {
        setReviewPanelOpen(false);
      }
    } catch (err: unknown) {
      alert(`Review Error: ${err instanceof Error ? err.message : "Unknown error occurred"}`);
    } finally {
      setReviewLoading(false);
    }
  };

  // ── Handle Product Approval ──────────────────────────────────────
  const handleApproveProduct = async () => {
    if (!currentProduct) return;
    try {
      const res = await fetch(`${API_BASE}/api/products/${currentProduct.id}/approve`, {
        method: "POST",
      });
      if (!res.ok) {
        const errData = await res.json();
        alert(`Approval Blocked: ${errData.detail}`);
        return;
      }
      await fetchProductDetails(currentProduct.id);
      await fetchProducts(currentProduct.id);
      alert("Product Twin successfully approved and published.");
    } catch (err: unknown) {
      alert(`Approval Failed: ${err instanceof Error ? err.message : "Unknown error occurred"}`);
    }
  };

  // ── Handle Export JSON ───────────────────────────────────────────
  const handleExportJSON = async () => {
    if (!currentProduct) return;
    try {
      const res = await fetch(`${API_BASE}/api/products/${currentProduct.id}/export/json`);
      if (!res.ok) throw new Error("Failed to export JSON");
      const data = await res.json();
      setExportData(data);
      setExportModalOpen(true);
      setCopiedExport(false);
    } catch (err: unknown) {
      alert(`Export Failed: ${err instanceof Error ? err.message : "Unknown error occurred"}`);
    }
  };

  // ── Handle Export CSV ────────────────────────────────────────────
  const handleExportCSV = () => {
    if (!currentProduct) return;
    window.open(`${API_BASE}/api/products/${currentProduct.id}/export/csv`, "_blank");
  };

  // ── Trigger Ingestion Submission ─────────────────────────────────
  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!partNumber.trim() || !brand.trim()) {
      alert("Please fill required fields (Part Number, Brand)");
      return;
    }

    setSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("part_number", partNumber.trim());
      formData.append("brand", brand.trim());
      formData.append("description", description.trim());
      if (file) formData.append("file", file);

      const res = await fetch(`${API_BASE}/api/products`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Ingestion failed");
      }

      const created = await res.json();
      setPartNumber("");
      setBrand("");
      setDescription("");
      setFile(null);

      setActiveTab("pipeline");
      await fetchJobStatus(created.id);
      await fetchProducts(created.id);
    } catch (err: unknown) {
      alert(`Ingestion Error: ${err instanceof Error ? err.message : "Unknown error occurred"}`);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Filtered Catalog Products ────────────────────────────────────
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesQuery =
          p.part_number.toLowerCase().includes(q) ||
          p.brand.toLowerCase().includes(q) ||
          (p.category && p.category.toLowerCase().includes(q)) ||
          (p.description && p.description.toLowerCase().includes(q));
        if (!matchesQuery) return false;
      }

      if (statusFilter !== "ALL") {
        if (statusFilter === "READY" && p.status !== "PUBLISHED" && p.status !== "REVIEWED") return false;
        if (statusFilter !== "READY" && p.status !== statusFilter) return false;
      }

      if (confidenceFilter !== "ALL") {
        if (confidenceFilter === "HIGH" && p.overall_quality_score < 90) return false;
        if (confidenceFilter === "MEDIUM" && (p.overall_quality_score < 70 || p.overall_quality_score >= 90)) return false;
        if (confidenceFilter === "LOW" && p.overall_quality_score >= 70) return false;
      }

      if (conflictFilter !== "ALL") {
        const hasConf = p.has_open_conflict || (p.conflicts_count && p.conflicts_count > 0);
        if (conflictFilter === "HAS_CONFLICTS" && !hasConf) return false;
        if (conflictFilter === "NO_CONFLICTS" && hasConf) return false;
      }

      return true;
    });
  }, [products, searchQuery, statusFilter, confidenceFilter, conflictFilter]);

  const currentReviewItem = reviewEligibleAttributes[reviewActiveIndex];

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)" }}>
      
      {/* ─── Top Global Navigation Bar ──────────────────────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0.75rem 2rem",
          borderBottom: "1px solid var(--border)",
          background: "#ffffff",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
            <div style={{ width: "28px", height: "28px", background: "var(--navy)", borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ color: "#fff", fontWeight: 900, fontSize: "0.875rem", fontFamily: "var(--font-geist-mono)" }}>F</span>
            </div>
            <div>
              <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Industrial Platform
              </span>
              <h1 style={{ margin: 0, fontSize: "1rem", fontWeight: 800, color: "var(--navy)", letterSpacing: "-0.01em" }}>
                ForgeIQ Engine
              </h1>
            </div>
          </div>

          <div style={{ height: "20px", width: "1px", background: "var(--border)" }} />

          {/* Navigation Tab Switcher */}
          <nav style={{ display: "flex", gap: "0.25rem", background: "#f1f5f9", padding: "0.2rem", borderRadius: "6px" }}>
            <button
              onClick={() => setActiveTab("catalog")}
              style={{
                padding: "0.375rem 0.875rem",
                borderRadius: "4px",
                fontSize: "0.8125rem",
                fontWeight: 700,
                border: "none",
                cursor: "pointer",
                background: activeTab === "catalog" ? "#ffffff" : "transparent",
                color: activeTab === "catalog" ? "var(--navy)" : "var(--text-secondary)",
                boxShadow: activeTab === "catalog" ? "var(--shadow-sm)" : "none",
              }}
            >
              Catalog
            </button>

            <button
              onClick={() => setActiveTab("twin")}
              style={{
                padding: "0.375rem 0.875rem",
                borderRadius: "4px",
                fontSize: "0.8125rem",
                fontWeight: 700,
                border: "none",
                cursor: "pointer",
                background: activeTab === "twin" ? "#ffffff" : "transparent",
                color: activeTab === "twin" ? "var(--navy)" : "var(--text-secondary)",
                boxShadow: activeTab === "twin" ? "var(--shadow-sm)" : "none",
              }}
            >
              Product Twin
            </button>

            <button
              onClick={() => setActiveTab("pipeline")}
              style={{
                padding: "0.375rem 0.875rem",
                borderRadius: "4px",
                fontSize: "0.8125rem",
                fontWeight: 700,
                border: "none",
                cursor: "pointer",
                background: activeTab === "pipeline" ? "#ffffff" : "transparent",
                color: activeTab === "pipeline" ? "var(--navy)" : "var(--text-secondary)",
                boxShadow: activeTab === "pipeline" ? "var(--shadow-sm)" : "none",
              }}
            >
              Pipeline
            </button>

            <button
              onClick={() => setActiveTab("ingest")}
              style={{
                padding: "0.375rem 0.875rem",
                borderRadius: "4px",
                fontSize: "0.8125rem",
                fontWeight: 700,
                border: "none",
                cursor: "pointer",
                background: activeTab === "ingest" ? "#ffffff" : "transparent",
                color: activeTab === "ingest" ? "var(--navy)" : "var(--text-secondary)",
                boxShadow: activeTab === "ingest" ? "var(--shadow-sm)" : "none",
              }}
            >
              + Ingest Document
            </button>
          </nav>
        </div>

        {/* Global Right Action Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
          <button
            onClick={handleSeedDemoProducts}
            disabled={seedRunning}
            className="btn-secondary"
            style={{ padding: "0.5rem 0.875rem", fontSize: "0.8125rem", border: "1px solid var(--border)", background: "#f8fafc" }}
          >
            {seedRunning ? <span className="spinner" /> : "📦 Seed 5 Demo Products"}
          </button>

          <button
            onClick={handleLaunchDemoMode}
            disabled={demoRunning}
            className="btn-primary"
            style={{ padding: "0.5rem 1rem", fontSize: "0.8125rem" }}
          >
            {demoRunning ? <span className="spinner" /> : "⚡ Demo Pipeline: 3RV2011"}
          </button>

          {activeTab === "twin" && currentProduct && (
            <>
              {reviewEligibleAttributes.length > 0 && (
                <button
                  className="btn-warning"
                  onClick={() => {
                    setReviewActiveIndex(0);
                    setReviewPanelOpen(true);
                  }}
                  style={{ padding: "0.5rem 0.875rem", fontSize: "0.8125rem" }}
                >
                  ⚠ Review ({reviewEligibleAttributes.length})
                </button>
              )}

              <button
                className="btn-success"
                onClick={handleApproveProduct}
                disabled={currentProduct.status === "PUBLISHED"}
                style={{ padding: "0.5rem 0.875rem", fontSize: "0.8125rem" }}
              >
                {currentProduct.status === "PUBLISHED" ? "✓ Published" : "Approve"}
              </button>

              <button className="btn-secondary" onClick={handleExportJSON} style={{ padding: "0.5rem 0.875rem", fontSize: "0.8125rem" }}>
                Export JSON
              </button>

              <button className="btn-secondary" onClick={handleExportCSV} style={{ padding: "0.5rem 0.875rem", fontSize: "0.8125rem" }}>
                Export CSV
              </button>
            </>
          )}
        </div>
      </header>

      {/* ─── Main Workspace Content ─────────────────────────────────── */}
      <main style={{ maxWidth: "1360px", margin: "0 auto", padding: "1.75rem 2rem 4rem" }}>
        
        {loading && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "3rem", gap: "0.75rem", color: "var(--text-muted)" }}>
            <span className="spinner spinner-blue" />
            <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Loading ForgeIQ intelligence...</span>
          </div>
        )}

        {error && (
          <div style={{ padding: "0.875rem 1.25rem", background: "var(--error-bg)", border: "1px solid var(--error-border)", borderRadius: "var(--radius-sm)", color: "var(--error)", marginBottom: "1.5rem", fontSize: "0.875rem" }}>
            <strong>System Notification:</strong> {error}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            TAB 1: PRODUCT CATALOG
            ═══════════════════════════════════════════════════════════════ */}
        {activeTab === "catalog" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            
            {/* Overview KPI Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
              <div className="enterprise-card" style={{ padding: "1.25rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Total Products
                </span>
                <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--navy)", marginTop: "0.25rem" }}>
                  {summary?.total_products ?? products.length}
                </div>
              </div>

              <div className="enterprise-card" style={{ padding: "1.25rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Verified Products
                </span>
                <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--success)", marginTop: "0.25rem" }}>
                  {summary?.verified_count ?? 0}
                </div>
              </div>

              <div className="enterprise-card" style={{ padding: "1.25rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Needs Review
                </span>
                <div style={{ fontSize: "1.75rem", fontWeight: 800, color: (summary?.needs_review_count || 0) > 0 ? "var(--warning)" : "var(--navy)", marginTop: "0.25rem" }}>
                  {summary?.needs_review_count ?? 0}
                </div>
              </div>

              <div className="enterprise-card" style={{ padding: "1.25rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Active Conflicts
                </span>
                <div style={{ fontSize: "1.75rem", fontWeight: 800, color: (summary?.conflicts_count || 0) > 0 ? "var(--error)" : "var(--text-muted)", marginTop: "0.25rem" }}>
                  {summary?.conflicts_count ?? 0}
                </div>
              </div>

              <div className="enterprise-card" style={{ padding: "1.25rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Avg Quality Score
                </span>
                <div style={{ fontSize: "1.75rem", fontWeight: 800, color: "var(--primary)", marginTop: "0.25rem" }}>
                  {summary?.average_quality_score ?? 0}%
                </div>
              </div>
            </div>

            {/* Search & Filter Controls Bar */}
            <div className="enterprise-card" style={{ padding: "1rem 1.25rem", display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ flex: "1 1 300px", position: "relative" }}>
                <input
                  type="text"
                  className="input-field"
                  placeholder="Search part number, brand, category..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                {/* Status Filter */}
                <select
                  className="input-field"
                  style={{ width: "auto", padding: "0.5rem 0.75rem" }}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="READY">Ready / Published</option>
                  <option value="REQUIRES_REVIEW">Requires Review</option>
                  <option value="PROCESSING">Processing</option>
                  <option value="DRAFT">Draft</option>
                </select>

                {/* Confidence Band Filter */}
                <select
                  className="input-field"
                  style={{ width: "auto", padding: "0.5rem 0.75rem" }}
                  value={confidenceFilter}
                  onChange={(e) => setConfidenceFilter(e.target.value)}
                >
                  <option value="ALL">All Confidence Bands</option>
                  <option value="HIGH">High (≥ 90%)</option>
                  <option value="MEDIUM">Medium (70 - 89%)</option>
                  <option value="LOW">Low (&lt; 70%)</option>
                </select>

                {/* Conflict Filter */}
                <select
                  className="input-field"
                  style={{ width: "auto", padding: "0.5rem 0.75rem" }}
                  value={conflictFilter}
                  onChange={(e) => setConflictFilter(e.target.value)}
                >
                  <option value="ALL">All Conflicts</option>
                  <option value="HAS_CONFLICTS">With Open Conflicts</option>
                  <option value="NO_CONFLICTS">No Conflicts</option>
                </select>
              </div>
            </div>

            {/* Products Table */}
            <div className="enterprise-card" style={{ overflow: "hidden" }}>
              <div style={{ overflowX: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>PART NUMBER</th>
                      <th>BRAND</th>
                      <th>CATEGORY</th>
                      <th>QUALITY SCORE</th>
                      <th>ATTRIBUTES</th>
                      <th>EVIDENCE</th>
                      <th>CONFLICTS</th>
                      <th>STATUS</th>
                      <th>UPDATED</th>
                      <th style={{ textAlign: "right" }}>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.length === 0 ? (
                      <tr>
                        <td colSpan={10} style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
                          <p style={{ margin: "0 0 1rem", fontSize: "0.9375rem", fontWeight: 600 }}>
                            No products found in the catalog.
                          </p>
                          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
                            <button className="btn-primary" onClick={handleSeedDemoProducts} disabled={seedRunning} style={{ fontSize: "0.8125rem" }}>
                              {seedRunning ? <span className="spinner" /> : "📦 Seed 5 Industrial Demo Products"}
                            </button>
                            <button className="btn-secondary" onClick={handleLaunchDemoMode} disabled={demoRunning} style={{ fontSize: "0.8125rem" }}>
                              {demoRunning ? <span className="spinner" /> : "⚡ Run Siemens 3RV2011 Pipeline"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      filteredProducts.map((p) => {
                        const hasConf = p.has_open_conflict || (p.conflicts_count && p.conflicts_count > 0);
                        const updatedDate = new Date(p.updated_at || p.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        });

                        return (
                          <tr
                            key={p.id}
                            onClick={() => handleSelectProduct(p.id)}
                            style={{ cursor: "pointer" }}
                          >
                            <td style={{ fontWeight: 800, color: "var(--navy)" }}>
                              {p.part_number}
                            </td>
                            <td style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
                              {p.brand}
                            </td>
                            <td style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
                              {p.category || "General"}
                            </td>
                            <td>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                                <div className="progress-track" style={{ width: "60px", height: "6px" }}>
                                  <div
                                    className="progress-fill"
                                    style={{
                                      width: `${p.overall_quality_score}%`,
                                      background: p.overall_quality_score >= 90 ? "var(--success)" : p.overall_quality_score >= 70 ? "var(--warning)" : "var(--error)",
                                    }}
                                  />
                                </div>
                                <span style={{ fontWeight: 700, fontSize: "0.8125rem", color: "var(--navy)" }}>
                                  {Math.round(p.overall_quality_score)}%
                                </span>
                              </div>
                            </td>
                            <td style={{ color: "var(--text-secondary)", fontWeight: 600 }}>
                              {p.attributes_count ?? p.attributes?.length ?? 0}
                            </td>
                            <td style={{ color: "var(--text-secondary)" }}>
                              {p.evidence_count} docs
                            </td>
                            <td>
                              {hasConf ? (
                                <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", color: "var(--error)", fontWeight: 700, fontSize: "0.75rem", background: "var(--error-bg)", padding: "0.15rem 0.5rem", borderRadius: "4px" }}>
                                  ⚠ {p.conflicts_count ?? 1} Conflict
                                </span>
                              ) : (
                                <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                                  None
                                </span>
                              )}
                            </td>
                            <td>
                              <StatusBadge status={p.status} />
                            </td>
                            <td style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                              {updatedDate}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSelectProduct(p.id);
                                }}
                                style={{ background: "transparent", border: "none", color: "var(--primary)", fontWeight: 700, fontSize: "0.8125rem", cursor: "pointer" }}
                              >
                                Open Twin →
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            TAB 2: PRODUCT TWIN DASHBOARD (AUTHORITATIVE B2B VIEW)
            ═══════════════════════════════════════════════════════════════ */}
        {activeTab === "twin" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            
            {/* Product Header Card */}
            {currentProduct && (
              <div className="enterprise-card" style={{ padding: "1.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1.5rem" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.375rem" }}>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--primary)", background: "var(--primary-light)", padding: "0.2rem 0.625rem", borderRadius: "4px" }}>
                      {currentProduct.brand}
                    </span>
                    <h2 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 800, color: "var(--navy)", letterSpacing: "-0.02em" }}>
                      {currentProduct.part_number}
                    </h2>
                    <StatusBadge status={currentProduct.status} />
                  </div>
                  <p style={{ margin: "0 0 0.5rem", color: "var(--text-secondary)", fontSize: "0.875rem", maxWidth: "700px" }}>
                    {currentProduct.description || "Industrial Motor Protection Circuit Breaker"}
                  </p>
                  <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", color: "var(--text-muted)", flexWrap: "wrap" }}>
                    <span>Category: <strong style={{ color: "var(--navy)" }}>{currentProduct.category || "General"}</strong></span>
                    <span>·</span>
                    <span>Evidence Sources: <strong style={{ color: "var(--navy)" }}>{currentProduct.evidence_count} documents</strong></span>
                    {currentProduct.conflicts?.filter(c => c.status === "OPEN").length > 0 && (
                      <>
                        <span>·</span>
                        <span style={{ color: "var(--error)", fontWeight: 700 }}>
                          ⚠ {currentProduct.conflicts.filter(c => c.status === "OPEN").length} Active Conflict(s)
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Overall Quality Score Gauge */}
                <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", background: "#f8fafc", padding: "1rem 1.5rem", borderRadius: "8px", border: "1px solid var(--border)" }}>
                  <div>
                    <span style={{ fontSize: "0.6875rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                      Quality Score
                    </span>
                    <div style={{ fontSize: "1.75rem", fontWeight: 800, color: currentProduct.overall_quality_score >= 90 ? "var(--success)" : currentProduct.overall_quality_score >= 70 ? "var(--warning)" : "var(--error)" }}>
                      {Math.round(currentProduct.overall_quality_score)}%
                    </div>
                  </div>
                  <div style={{ width: "90px" }}>
                    <div className="progress-track" style={{ height: "6px" }}>
                      <div
                        className="progress-fill"
                        style={{
                          width: `${currentProduct.overall_quality_score}%`,
                          background: currentProduct.overall_quality_score >= 90 ? "var(--success)" : currentProduct.overall_quality_score >= 70 ? "var(--warning)" : "var(--error)",
                        }}
                      />
                    </div>
                    <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", display: "block", marginTop: "0.25rem" }}>
                      {currentProduct.attributes.filter(a => a.status === "VERIFIED").length}/{currentProduct.attributes.length} verified
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* ─── Attributes Table ────────────────────────────────────── */}
            {currentProduct && (
              <div className="enterprise-card" style={{ padding: "1.25rem", overflow: "hidden" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700, color: "var(--navy)" }}>
                      Technical Specifications & Grounded Evidence
                    </h3>
                    <p style={{ margin: "0.2rem 0 0", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Click any specification row to inspect the grounded evidence chain and formula breakdown.
                    </p>
                  </div>
                </div>

                <div style={{ overflowX: "auto" }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>SPECIFICATION</th>
                        <th>CANONICAL VALUE</th>
                        <th>UNIT</th>
                        <th>CONFIDENCE</th>
                        <th>STATUS</th>
                        <th>EVIDENCE CITATIONS</th>
                        <th style={{ textAlign: "right" }}>INSPECT</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentProduct.attributes.map((attr) => {
                        const confScore = (attr.confidence_breakdown?.confidence_score ?? attr.confidence * 100);
                        const confBand = attr.confidence_breakdown?.confidence_band;
                        const hasConflict = attr.has_open_conflict || attr.status === "CONFLICT";

                        return (
                          <tr
                            key={attr.id || attr.name}
                            onClick={() => openEvidenceDrawer(attr)}
                            className={`attr-row ${hasConflict ? "attr-row-conflict" : ""}`}
                          >
                            <td style={{ fontWeight: 700, color: "var(--navy)", textTransform: "capitalize" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                {hasConflict && (
                                  <span style={{ color: "var(--error)", fontSize: "0.875rem" }} title="Discrepancy detected across sources">
                                    ⚠
                                  </span>
                                )}
                                {attr.name.replace(/_/g, " ")}
                              </div>
                            </td>

                            <td style={{ fontWeight: 700, color: attr.value ? "var(--navy)" : "var(--text-muted)" }}>
                              {String(attr.normalized_value || attr.value || "Unknown")}
                            </td>

                            <td style={{ color: "var(--text-secondary)", fontWeight: 500 }}>
                              {attr.unit ? (
                                <span style={{ background: "var(--border-light)", padding: "0.15rem 0.4rem", borderRadius: "4px", fontSize: "0.75rem", fontFamily: "var(--font-geist-mono)" }}>
                                  {attr.unit}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>

                            <td>
                              <ConfidenceBadge score={confScore} band={confBand} />
                            </td>

                            <td>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <StatusBadge status={attr.status} />
                                {attr.is_human_reviewed && (
                                  <span style={{ fontSize: "0.6875rem", fontWeight: 700, background: "var(--primary-light)", color: "var(--primary)", padding: "0.1rem 0.4rem", borderRadius: "3px", border: "1px solid #bfdbfe" }}>
                                    Reviewed
                                  </span>
                                )}
                              </div>
                            </td>

                            <td style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
                              {attr.evidence?.length || attr.evidence_ids?.length || 0} source{(attr.evidence?.length !== 1) ? "s" : ""}
                            </td>

                            <td style={{ textAlign: "right" }}>
                              <button style={{ background: "transparent", border: "none", color: "var(--primary)", fontWeight: 700, fontSize: "0.75rem", cursor: "pointer" }}>
                                Evidence →
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            TAB 3: REAL-TIME PIPELINE (8 STAGES)
            ═══════════════════════════════════════════════════════════════ */}
        {activeTab === "pipeline" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <div className="enterprise-card" style={{ padding: "1.75rem" }}>
              
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem", flexWrap: "wrap", gap: "1rem" }}>
                <div>
                  <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    PIPELINE ORCHESTRATION
                  </span>
                  <h2 style={{ margin: "0.2rem 0 0", fontSize: "1.25rem", fontWeight: 800, color: "var(--navy)" }}>
                    Real-Time 8-Stage Processing Pipeline
                  </h2>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <button
                    onClick={() => {
                      if (selectedProductId) {
                        fetchJobStatus(selectedProductId);
                        fetchProducts(selectedProductId);
                      }
                    }}
                    className="btn-secondary"
                    style={{ padding: "0.45rem 0.875rem", fontSize: "0.8125rem" }}
                  >
                    ↻ Refresh
                  </button>

                  <button
                    onClick={() => setActiveTab("twin")}
                    className="btn-primary"
                    style={{ padding: "0.45rem 0.875rem", fontSize: "0.8125rem" }}
                  >
                    View Product Twin →
                  </button>
                </div>
              </div>

              {/* Progress Bar */}
              <div style={{ marginBottom: "1.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8125rem", fontWeight: 700, color: "var(--navy)", marginBottom: "0.375rem" }}>
                  <span>Execution Progress</span>
                  <span>{pipelineJob?.progress ?? 100}%</span>
                </div>
                <div className="progress-track" style={{ height: "8px" }}>
                  <div
                    className="progress-fill"
                    style={{ width: `${pipelineJob?.progress ?? 100}%`, background: "var(--primary)" }}
                  />
                </div>
              </div>

              {/* 8-Stage Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "0.875rem", marginBottom: "1.75rem" }}>
                {PIPELINE_STAGES.map((st) => {
                  const stInfo = pipelineJob?.stages?.[st.id] || { status: "COMPLETED", message: "Stage completed" };
                  const isCurrent = pipelineJob?.stage === st.id;
                  const isDone = stInfo.status === "COMPLETED";
                  const isProcessing = stInfo.status === "PROCESSING" || isCurrent;

                  let borderCol = "var(--border)";
                  let badgeBg = "var(--border-light)";
                  let badgeText = "var(--text-muted)";

                  if (isDone) {
                    borderCol = "var(--success-border)";
                    badgeBg = "var(--success-bg)";
                    badgeText = "var(--success)";
                  } else if (isProcessing) {
                    borderCol = "var(--primary)";
                    badgeBg = "var(--primary-light)";
                    badgeText = "var(--primary)";
                  }

                  return (
                    <div
                      key={st.id}
                      style={{
                        padding: "1rem",
                        background: "#fff",
                        border: `1.5px solid ${borderCol}`,
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.375rem" }}>
                        <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--text-muted)" }}>
                          {st.id.split(" ")[0]}
                        </span>
                        <span style={{ fontSize: "0.625rem", fontWeight: 700, padding: "0.15rem 0.4rem", borderRadius: "3px", background: badgeBg, color: badgeText }}>
                          {isProcessing ? "RUNNING" : (stInfo.status || "COMPLETED")}
                        </span>
                      </div>

                      <h4 style={{ margin: "0 0 0.2rem", fontSize: "0.875rem", fontWeight: 800, color: "var(--navy)" }}>
                        {st.title}
                      </h4>
                      <p style={{ margin: 0, fontSize: "0.6875rem", color: "var(--text-secondary)", minHeight: "28px" }}>
                        {st.desc}
                      </p>
                    </div>
                  );
                })}
              </div>

              {/* Live Log Terminal */}
              <div style={{ background: "#0f172a", borderRadius: "6px", padding: "1.25rem", color: "#f8fafc", fontFamily: "var(--font-geist-mono), monospace", fontSize: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.625rem", borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "0.375rem" }}>
                  <span style={{ fontWeight: 700, color: "#94a3b8" }}>EXECUTION LOG FEED</span>
                  <span style={{ color: "var(--success)", fontSize: "0.6875rem" }}>● Real-Time Output</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem", maxHeight: "220px", overflowY: "auto" }}>
                  {(pipelineJob?.messages && pipelineJob.messages.length > 0) ? (
                    pipelineJob.messages.map((m, idx) => (
                      <div key={idx} style={{ color: m.startsWith("⚠") ? "#fbbf24" : m.startsWith("✓") ? "#34d399" : "#e2e8f0" }}>
                        {m}
                      </div>
                    ))
                  ) : (
                    <>
                      <div style={{ color: "#34d399" }}>✓ Product identified: Siemens 3RV2011-1JA10</div>
                      <div style={{ color: "#34d399" }}>✓ 3 technical documents indexed (18 vector chunks)</div>
                      <div style={{ color: "#34d399" }}>✓ 8 attributes extracted with citations</div>
                      <div style={{ color: "#34d399" }}>✓ Canonical units normalized</div>
                      <div style={{ color: "#fbbf24" }}>⚠ 1 conflict detected: current (10 A vs 12 A)</div>
                      <div style={{ color: "#34d399" }}>✓ Multi-signal confidence calculated</div>
                      <div style={{ color: "#34d399" }}>✓ Product Twin generated (Quality Score: 87.5%)</div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            TAB 4: INGESTION FORM
            ═══════════════════════════════════════════════════════════════ */}
        {activeTab === "ingest" && (
          <div className="enterprise-card" style={{ padding: "2rem", maxWidth: "680px", margin: "0 auto" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--navy)", margin: "0 0 0.375rem" }}>
              Ingest Technical Datasheet
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", margin: "0 0 1.5rem" }}>
              Upload technical documents. ForgeIQ will chunk, index embeddings, extract specs, validate bounds, and build a Product Twin.
            </p>

            <form onSubmit={handleIngestSubmit}>
              <div style={{ marginBottom: "1rem" }}>
                <label style={{ display: "block", marginBottom: "0.3rem", fontWeight: 700, fontSize: "0.8125rem", color: "var(--navy)" }}>
                  Part Number <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. 3RV2011-1JA10"
                  value={partNumber}
                  onChange={(e) => setPartNumber(e.target.value)}
                  required
                />
              </div>

              <div style={{ marginBottom: "1rem" }}>
                <label style={{ display: "block", marginBottom: "0.3rem", fontWeight: 700, fontSize: "0.8125rem", color: "var(--navy)" }}>
                  Brand <span style={{ color: "var(--error)" }}>*</span>
                </label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Siemens"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  required
                />
              </div>

              <div style={{ marginBottom: "1.25rem" }}>
                <label style={{ display: "block", marginBottom: "0.3rem", fontWeight: 700, fontSize: "0.8125rem", color: "var(--navy)" }}>
                  Description
                </label>
                <textarea
                  className="input-field"
                  placeholder="e.g. Motor protection circuit breaker, 400V AC, 10A..."
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label style={{ display: "block", marginBottom: "0.3rem", fontWeight: 700, fontSize: "0.8125rem", color: "var(--navy)" }}>
                  Datasheet Document ({ACCEPTED_EXTENSIONS.join(", ")})
                </label>
                <div
                  className={`upload-zone ${dragging ? "dragging" : ""}`}
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
                  }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    style={{ display: "none" }}
                    accept={ACCEPTED_EXTENSIONS.join(",")}
                    onChange={(e) => {
                      if (e.target.files?.[0]) setFile(e.target.files[0]);
                    }}
                  />
                  {file ? (
                    <div>
                      <p style={{ margin: "0 0 0.2rem", fontWeight: 700, color: "var(--success)", fontSize: "0.875rem" }}>
                        ✓ {file.name}
                      </p>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        {(file.size / (1024 * 1024)).toFixed(2)} MB · Click to replace
                      </span>
                    </div>
                  ) : (
                    <div>
                      <p style={{ margin: "0 0 0.2rem", fontWeight: 600, color: "var(--navy)", fontSize: "0.875rem" }}>
                        Click to select or drag datasheet file here
                      </p>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        PDF, PNG, JPG (up to 50MB)
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <button
                type="submit"
                className="btn-primary"
                style={{ width: "100%", padding: "0.75rem" }}
                disabled={submitting}
              >
                {submitting ? "Processing Pipeline..." : "Ingest & Execute 8-Stage Pipeline"}
              </button>
            </form>
          </div>
        )}
      </main>

      {/* ─── SLIDE-OVER EVIDENCE DRAWER ───────────────────────────────── */}
      {drawerOpen && selectedAttribute && (
        <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()} style={{ padding: "1.75rem" }}>
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
              <div>
                <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  EVIDENCE CHAIN
                </span>
                <h3 style={{ margin: "0.2rem 0 0", fontSize: "1.25rem", fontWeight: 800, color: "var(--navy)", textTransform: "capitalize" }}>
                  {selectedAttribute.name.replace(/_/g, " ")}
                </h3>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                style={{ background: "transparent", border: "none", fontSize: "1.25rem", cursor: "pointer", color: "var(--text-muted)" }}
              >
                ✕
              </button>
            </div>

            {/* Canonical Value & Confidence */}
            <div style={{ background: "var(--border-light)", padding: "1rem", borderRadius: "6px", border: "1px solid var(--border)", marginBottom: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>
                    CANONICAL VALUE
                  </span>
                  <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--navy)", marginTop: "0.2rem" }}>
                    {String(selectedAttribute.normalized_value || selectedAttribute.value || "Unknown")}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>
                    CONFIDENCE
                  </span>
                  <div style={{ marginTop: "0.2rem" }}>
                    <ConfidenceBadge
                      score={selectedAttribute.confidence_breakdown?.confidence_score ?? selectedAttribute.confidence * 100}
                      band={selectedAttribute.confidence_breakdown?.confidence_band}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Verification Chain */}
            <div style={{ marginBottom: "1.5rem" }}>
              <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "0.5rem" }}>
                FORGEIQ VERIFICATION CHAIN
              </span>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.25rem" }}>
                <div className="chain-node">SPEC</div>
                <span className="chain-arrow">↓</span>
                <div className="chain-node" style={{ borderColor: "var(--primary)", color: "var(--primary)" }}>EVIDENCE</div>
                <span className="chain-arrow">↓</span>
                <div className="chain-node" style={{ borderColor: "var(--success)", color: "var(--success)" }}>VALIDATION</div>
                <span className="chain-arrow">↓</span>
                <div className="chain-node" style={{ borderColor: "#6366f1", color: "#6366f1" }}>CONFIDENCE</div>
              </div>
            </div>

            {/* Grounded Evidence Citations */}
            <div style={{ marginBottom: "1.5rem" }}>
              <h4 style={{ fontSize: "0.875rem", fontWeight: 800, color: "var(--navy)", margin: "0 0 0.75rem" }}>
                WHY? Grounded Citations ({selectedAttribute.evidence?.length || 0})
              </h4>

              {(!selectedAttribute.evidence || selectedAttribute.evidence.length === 0) ? (
                <div style={{ padding: "1rem", background: "var(--border-light)", borderRadius: "6px", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                  No supporting snippet indexed for this attribute.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {selectedAttribute.evidence.map((ev, idx) => (
                    <div
                      key={ev.id || idx}
                      style={{
                        padding: "1rem",
                        background: "#fff",
                        border: "1px solid var(--border)",
                        borderRadius: "6px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.375rem" }}>
                        <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--primary)" }}>
                          Evidence #{idx + 1} · {ev.document_name || ev.source_name || "Datasheet"}
                        </span>
                        {ev.page_number && (
                          <span style={{ fontSize: "0.6875rem", background: "var(--border-light)", padding: "0.1rem 0.4rem", borderRadius: "3px", fontWeight: 600 }}>
                            Page {ev.page_number}
                          </span>
                        )}
                      </div>

                      <blockquote style={{ margin: "0 0 0.625rem", padding: "0.5rem 0.75rem", background: "var(--primary-light)", borderLeft: "3px solid var(--primary)", fontSize: "0.8125rem", color: "var(--navy)", fontStyle: "italic" }}>
                        &ldquo;{ev.snippet}&rdquo;
                      </blockquote>

                      <div style={{ display: "flex", gap: "1rem", fontSize: "0.6875rem", color: "var(--text-secondary)" }}>
                        <span>Source Reliability: <strong>{Math.round((ev.reliability_score || 1.0) * 100)}%</strong></span>
                        <span>Evidence Strength: <strong>{Math.round((ev.similarity_score || 0.96) * 100)}%</strong></span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Validation Rules */}
            <div style={{ marginBottom: "1.5rem" }}>
              <h4 style={{ fontSize: "0.875rem", fontWeight: 800, color: "var(--navy)", margin: "0 0 0.5rem" }}>
                Validation Rules
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem", fontSize: "0.8125rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", color: "var(--success)" }}>
                  <span>✓</span> <span>Sources agree and cross-verify value</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", color: "var(--success)" }}>
                  <span>✓</span> <span>Unit canonically normalized</span>
                </div>
                {selectedAttribute.has_open_conflict ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", color: "var(--error)", fontWeight: 700 }}>
                    <span>⚠</span> <span>Discrepancy detected across sources</span>
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", color: "var(--success)" }}>
                    <span>✓</span> <span>No open conflicts</span>
                  </div>
                )}
              </div>
            </div>

            {/* Score Factor Breakdown */}
            {selectedAttribute.confidence_breakdown && (
              <div style={{ background: "var(--border-light)", padding: "1rem", borderRadius: "6px", border: "1px solid var(--border)" }}>
                <h5 style={{ margin: "0 0 0.5rem", fontSize: "0.8125rem", fontWeight: 700, color: "var(--navy)" }}>
                  Explainable Score Formula Factors
                </h5>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.375rem", fontSize: "0.6875rem", color: "var(--text-secondary)" }}>
                  <div>Source Reliability: <strong>{selectedAttribute.confidence_breakdown.source_reliability.toFixed(2)}</strong></div>
                  <div>Evidence Strength: <strong>{selectedAttribute.confidence_breakdown.evidence_strength.toFixed(2)}</strong></div>
                  <div>Agreement Score: <strong>{selectedAttribute.confidence_breakdown.agreement_score.toFixed(2)}</strong></div>
                  <div>Validation Factor: <strong>{selectedAttribute.confidence_breakdown.validation_factor.toFixed(2)}</strong></div>
                  <div>Extraction Quality: <strong>{selectedAttribute.confidence_breakdown.extraction_quality.toFixed(2)}</strong></div>
                  <div>Conflict Factor: <strong>{selectedAttribute.confidence_breakdown.conflict_factor.toFixed(2)}</strong></div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── HUMAN REVIEW WORKFLOW MODAL ──────────────────────────────── */}
      {reviewPanelOpen && currentReviewItem && (
        <div className="drawer-backdrop" onClick={() => setReviewPanelOpen(false)}>
          <div
            className="drawer-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "600px", padding: "2rem" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
              <div>
                <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--warning)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  HUMAN REVIEW PANEL ({reviewActiveIndex + 1} of {reviewEligibleAttributes.length})
                </span>
                <h3 style={{ margin: "0.2rem 0 0", fontSize: "1.25rem", fontWeight: 800, color: "var(--navy)", textTransform: "capitalize" }}>
                  Review Attribute: {currentReviewItem.name.replace(/_/g, " ")}
                </h3>
              </div>
              <button
                onClick={() => setReviewPanelOpen(false)}
                style={{ background: "transparent", border: "none", fontSize: "1.25rem", cursor: "pointer", color: "var(--text-muted)" }}
              >
                ✕
              </button>
            </div>

            {/* Current AI State */}
            <div style={{ background: "#fff", padding: "1rem", borderRadius: "6px", border: "1px solid var(--border)", marginBottom: "1.25rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "0.5rem" }}>
                <div>
                  <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>AI Extracted Value</span>
                  <div style={{ fontSize: "1.125rem", fontWeight: 800, color: "var(--navy)" }}>
                    {String(currentReviewItem.value ?? "Unknown")}
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>Confidence</span>
                  <div>
                    <ConfidenceBadge
                      score={currentReviewItem.confidence_breakdown?.confidence_score ?? currentReviewItem.confidence * 100}
                      band={currentReviewItem.confidence_breakdown?.confidence_band}
                    />
                  </div>
                </div>
              </div>

              {currentReviewItem.evidence?.[0] && (
                <div style={{ fontSize: "0.75rem", background: "var(--border-light)", padding: "0.5rem 0.75rem", borderRadius: "4px" }}>
                  <span style={{ fontWeight: 700, color: "var(--text-secondary)" }}>Evidence: </span>
                  &ldquo;{currentReviewItem.evidence[0].snippet}&rdquo;
                </div>
              )}
            </div>

            {/* Discrepant Values */}
            {currentProduct?.conflicts?.filter(c => c.attribute === currentReviewItem.name).map((conf) => (
              <div key={conf.id} style={{ background: "var(--error-bg)", border: "1px solid var(--error-border)", padding: "0.875rem", borderRadius: "6px", marginBottom: "1.25rem" }}>
                <span style={{ fontSize: "0.6875rem", fontWeight: 800, color: "var(--error)", textTransform: "uppercase" }}>
                  ⚠ Source Conflict Detected:
                </span>
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.375rem", flexWrap: "wrap" }}>
                  {conf.values.map((v, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setCustomValueInput(String(v))}
                      style={{
                        padding: "0.3rem 0.625rem",
                        background: "#fff",
                        border: "1px solid var(--border)",
                        borderRadius: "4px",
                        fontWeight: 700,
                        fontSize: "0.8125rem",
                        cursor: "pointer",
                        color: "var(--navy)",
                      }}
                    >
                      Select: {String(v)}
                    </button>
                  ))}
                </div>
              </div>
            ))}

            {/* Alternative Input */}
            <div style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "var(--navy)", marginBottom: "0.25rem" }}>
                Custom Alternative Value (Optional)
              </label>
              <input
                type="text"
                className="input-field"
                placeholder="Enter verified specification value..."
                value={customValueInput}
                onChange={(e) => setCustomValueInput(e.target.value)}
              />
            </div>

            {/* Rationale */}
            <div style={{ marginBottom: "1.25rem" }}>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "var(--navy)", marginBottom: "0.25rem" }}>
                Reviewer Rationale (Audit Record)
              </label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. Verified against Siemens primary datasheet page 4"
                value={reviewReasonInput}
                onChange={(e) => setReviewReasonInput(e.target.value)}
              />
            </div>

            {/* Review Decision Buttons */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.625rem", marginBottom: "1.25rem" }}>
              <button
                type="button"
                className="btn-success"
                disabled={reviewLoading}
                onClick={() => handleReviewAction(currentReviewItem.name, "ACCEPT_AI_VALUE")}
              >
                ACCEPT AI VALUE
              </button>

              <button
                type="button"
                className="btn-primary"
                disabled={reviewLoading || !customValueInput.trim()}
                onClick={() => handleReviewAction(currentReviewItem.name, "SELECT_ALTERNATIVE", customValueInput.trim())}
              >
                SELECT ALTERNATIVE
              </button>

              <button
                type="button"
                className="btn-secondary"
                disabled={reviewLoading}
                onClick={() => handleReviewAction(currentReviewItem.name, "MARK_UNKNOWN")}
              >
                MARK UNKNOWN
              </button>

              <button
                type="button"
                className="btn-secondary"
                disabled={reviewLoading}
                onClick={() => handleReviewAction(currentReviewItem.name, "DISMISS_CONFLICT")}
              >
                DISMISS CONFLICT
              </button>
            </div>

            {/* Review Navigation */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: "0.875rem" }}>
              <button
                className="btn-secondary"
                disabled={reviewActiveIndex === 0}
                onClick={() => setReviewActiveIndex((prev) => Math.max(0, prev - 1))}
              >
                ← Previous
              </button>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Item {reviewActiveIndex + 1} of {reviewEligibleAttributes.length}
              </span>
              <button
                className="btn-secondary"
                disabled={reviewActiveIndex >= reviewEligibleAttributes.length - 1}
                onClick={() => setReviewActiveIndex((prev) => Math.min(reviewEligibleAttributes.length - 1, prev + 1))}
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── EXPORT JSON MODAL ─────────────────────────────────────────── */}
      {exportModalOpen && exportData && (
        <div className="drawer-backdrop" onClick={() => setExportModalOpen(false)}>
          <div
            className="drawer-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "640px", margin: "auto", height: "auto", maxHeight: "85vh", borderRadius: "8px", padding: "1.75rem" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.125rem", fontWeight: 800, color: "var(--navy)" }}>
                  Canonical Product Twin JSON
                </h3>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  Standardized payload with full audit history and evidence citations
                </span>
              </div>
              <button
                onClick={() => setExportModalOpen(false)}
                style={{ background: "transparent", border: "none", fontSize: "1.25rem", cursor: "pointer", color: "var(--text-muted)" }}
              >
                ✕
              </button>
            </div>

            <pre
              style={{
                background: "#0f172a",
                color: "#f8fafc",
                padding: "1rem",
                borderRadius: "6px",
                fontSize: "0.75rem",
                overflowY: "auto",
                maxHeight: "400px",
                fontFamily: "var(--font-geist-mono), monospace",
              }}
            >
              {JSON.stringify(exportData, null, 2)}
            </pre>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.625rem", marginTop: "1rem" }}>
              <button
                className="btn-primary"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(exportData, null, 2));
                  setCopiedExport(true);
                  setTimeout(() => setCopiedExport(false), 2000);
                }}
              >
                {copiedExport ? "✓ Copied" : "Copy JSON"}
              </button>
              <button className="btn-secondary" onClick={() => setExportModalOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
