import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, products, documents, delivery, batch
from app.database import init_db
from app.config import settings
import app.models.product  # noqa: F401 — ensures models are loaded for init_db
import app.models.document  # noqa: F401 — ensures document tables are created

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("ForgeIQ API starting up…")
    logger.info(f"  Database : {settings.database_url}")
    logger.info(f"  AI Provider: {settings.ai_provider}")
    logger.info(f"  CORS origins: {settings.cors_origins_list}")

    # Ensure uploads directory exists
    os.makedirs(settings.uploads_path, exist_ok=True)

    init_db()
    logger.info("Database initialised ✓")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("ForgeIQ API shutting down.")


app = FastAPI(
    title="ForgeIQ API",
    description="Evidence-First AI Product Intelligence Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def read_root():
    return {
        "service": "ForgeIQ Engine API",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
    }


@app.get("/api", include_in_schema=False)
@app.get("/api/", include_in_schema=False)
def read_api_root():
    return {
        "service": "ForgeIQ Engine API",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }


# Mount health routes to both /health and /api/health
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(health.router, prefix="/api/health", tags=["Health"], include_in_schema=False)

# Core API routes
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(delivery.router, prefix="/api/delivery", tags=["Delivery"])
app.include_router(batch.router, prefix="/api/batch", tags=["Batch"])
