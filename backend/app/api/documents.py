from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.ingestion.pipeline import ingest_document

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    product_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Upload a document for text extraction and chunking.

    Returns document_id, filename, page_count, extracted_text_count, status.
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="No filename provided")

    # Validate extension
    import os
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read file
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"File too large ({file_size} bytes). Maximum is {MAX_FILE_SIZE} bytes.",
        )

    # Run ingestion pipeline
    result = ingest_document(
        db=db,
        file_bytes=file_bytes,
        filename=file.filename,
        file_size=file_size,
        product_id=product_id,
    )

    return result
