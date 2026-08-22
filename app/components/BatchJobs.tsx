"use client";
import React, { useState } from "react";
import * as api from "@/lib/api";
import type { BatchStatusResult } from "@/types/api";

export function BatchJobs() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<BatchStatusResult | null>(null);
  const [processing, setProcessing] = useState(false);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setProcessing(true);

    try {
      const data = await api.uploadBatch(file);
      pollChunk(data.job_id);
    } catch (err) {
      alert("Error: " + (err instanceof api.ApiError ? err.detail : (err instanceof Error ? err.message : err)));
      setProcessing(false);
    }
  };

  const pollChunk = async (id: string) => {
    try {
      const data = await api.processBatchChunk(id);
      setStatus(data);

      if (data.status !== "COMPLETED" && data.status !== "FAILED") {
        setTimeout(() => pollChunk(id), 1000);
      } else {
        setProcessing(false);
      }
    } catch (err) {
      console.error(err);
      setProcessing(false);
    }
  };

  return (
    <div className="enterprise-card" style={{ padding: "2rem", maxWidth: "680px", margin: "2rem auto" }}>
      <h2 style={{ fontSize: "1.5rem", fontWeight: 800, color: "var(--navy)", marginBottom: "1rem" }}>
        Batch Ingestion
      </h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: "2rem" }}>
        Upload a CSV of products to process them synchronously in small chunks (Vercel serverless limits).
      </p>

      <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <input 
          type="file" 
          accept=".csv" 
          onChange={e => setFile(e.target.files?.[0] || null)} 
          style={{ padding: "1rem", border: "1px dashed var(--border)", borderRadius: "6px" }}
        />
        <button type="submit" disabled={!file || processing} className="btn-primary">
          {processing ? "Processing Chunk..." : "Upload & Process"}
        </button>
      </form>

      {status && (
        <div style={{ marginTop: "2rem", padding: "1rem", background: "#f8fafc", borderRadius: "8px", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ fontWeight: 600 }}>Job Status: {status.status}</span>
            <span>{status.processed} / {status.total} processed</span>
          </div>
          <div style={{ width: "100%", height: "8px", background: "var(--border)", borderRadius: "4px", overflow: "hidden" }}>
            <div style={{ height: "100%", background: "var(--brand)", width: `${(status.processed / (status.total || 1)) * 100}%`, transition: "width 0.3s" }} />
          </div>
        </div>
      )}
    </div>
  );
}
