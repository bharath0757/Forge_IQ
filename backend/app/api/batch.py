"""
ForgeIQ Batch Processing API
Batch MUST use the same canonical enrichment pipeline as single-product mode.
"""
import uuid
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
import csv
import io

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job store for serverless compatibility.
# In production, use DB or Redis for persistence.
BATCH_JOBS: Dict[str, Dict[str, Any]] = {}


@router.post("/upload")
def upload_batch_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a CSV file to start a batch processing job.
    Validates and stores rows, returns a job ID for chunk processing.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    content_bytes = file.file.read()
    if len(content_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="File exceeds maximum allowed size of 50MB.")

    content = content_bytes.decode('utf-8')
    reader = csv.DictReader(io.StringIO(content))

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Empty CSV")

    job_id = f"batch_{uuid.uuid4().hex[:8]}"
    BATCH_JOBS[job_id] = {
        "id": job_id,
        "status": "PROCESSING",
        "total": len(rows),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
        "product_ids": [],
        "rows": rows,
    }

    return {"job_id": job_id, "total_rows": len(rows), "status": "CREATED"}


@router.get("/{job_id}/status")
def get_batch_status(job_id: str):
    """Return the current status of a batch job."""
    job = BATCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job["id"],
        "status": job["status"],
        "total": job["total"],
        "processed": job["processed"],
        "succeeded": job["succeeded"],
        "failed": job["failed"],
        "errors": job["errors"][-10:],  # Last 10 errors
        "product_ids": job["product_ids"],
    }


@router.post("/{job_id}/process_chunk")
def process_batch_chunk(job_id: str, chunk_size: int = 5, db: Session = Depends(get_db)):
    """
    Process a chunk of the batch using the SAME canonical enrichment pipeline.
    Each product goes through the full pipeline: clean → resolve → extract → normalize → validate → score → persist.
    """
    job = BATCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "COMPLETED":
        return {
            "status": "COMPLETED",
            "processed": job["processed"],
            "succeeded": job["succeeded"],
            "failed": job["failed"],
            "product_ids": job["product_ids"],
        }

    start = job["processed"]
    end = min(start + chunk_size, job["total"])

    rows_to_process = job["rows"][start:end]

    from app.services.pipeline_runner import get_pipeline_runner
    from app.normalization.entity_resolution import get_entity_resolution_service

    pipeline = get_pipeline_runner()
    resolver = get_entity_resolution_service()

    for row_idx, row in enumerate(rows_to_process, start=start + 1):
        try:
            # Extract fields from CSV row (support multiple column name conventions)
            mpn = row.get("Mfg_Part_Num", row.get("part_number", row.get("MPN", ""))).strip()
            brand_raw = row.get("Brand", row.get("brand", row.get("Manufacturer", ""))).strip()
            desc = row.get("Part_Desc", row.get("description", row.get("Description", ""))).strip()
            cat = row.get("Category", row.get("category", "")).strip()

            if not mpn:
                job["errors"].append(f"Row {row_idx}: Missing part number, skipped")
                job["failed"] += 1
                continue

            # Resolve brand via canonical entity resolution
            brand_result = resolver.resolve_brand(brand_raw)
            clean_brand = brand_result.canonical_value or brand_raw or "Unknown"

            product_id = f"prod_{uuid.uuid4().hex[:12]}"

            # Create a processing job for this product
            proc_job = pipeline.create_job(db, product_id)

            # Run the SAME canonical enrichment pipeline as single-product mode
            product = pipeline.run_pipeline(
                db=db,
                job_id=proc_job.id,
                product_id=product_id,
                part_number=mpn,
                brand=clean_brand,
                description=desc,
                category=cat or "General",
                raw_documents=None,  # Batch products typically don't have attached documents
            )

            job["product_ids"].append(product.id)
            job["succeeded"] += 1

        except Exception as e:
            logger.error(f"Batch row {row_idx} failed: {e}")
            job["errors"].append(f"Row {row_idx} ({mpn or 'unknown'}): {str(e)[:200]}")
            job["failed"] += 1

    job["processed"] = end
    if end >= job["total"]:
        job["status"] = "COMPLETED"

    return {
        "status": job["status"],
        "processed": job["processed"],
        "total": job["total"],
        "succeeded": job["succeeded"],
        "failed": job["failed"],
        "product_ids": job["product_ids"],
    }
