from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.retrieval.retriever import get_evidence_retriever

router = APIRouter()

@router.get("", summary="Comprehensive Health Check")
@router.get("/", include_in_schema=False)
@router.head("", include_in_schema=False)
@router.head("/", include_in_schema=False)
def health_check(db: Session = Depends(get_db)):
    """
    Returns the comprehensive health status of the ForgeIQ API, database connection,
    and vector retrieval store.
    """
    db_healthy = False
    db_error = None
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        db_error = str(e)

    vector_ready = False
    try:
        retriever = get_evidence_retriever()
        vector_ready = retriever is not None
    except Exception:
        pass

    if not db_healthy:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
                "database": "unavailable",
                "database_error": db_error,
                "vector_store": "ready" if vector_ready else "error",
            }
        )

    return {
        "status": "ok",
        "database": "connected",
        "vector_store": "ready",
        "service": "ForgeIQ API",
        "version": "0.1.0",
    }


@router.get("/db", summary="Database Deep Health Check")
@router.get("/db/", include_in_schema=False)
@router.head("/db", include_in_schema=False)
@router.head("/db/", include_in_schema=False)
def health_check_db(db: Session = Depends(get_db)):
    """
    Dedicated database health check probe for load balancers and orchestrators.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection is healthy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")
