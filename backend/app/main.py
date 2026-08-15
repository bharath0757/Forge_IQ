from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, products, documents
from app.database import init_db
from app.config import settings
import app.models.product  # noqa: F401 — ensures models are loaded for init_db
import app.models.document  # noqa: F401 — ensures document tables are created


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (if needed)


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

@app.get("/")
def read_root():
    return {
        "service": "ForgeIQ Engine API",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
    }

# Mount health routes to both /health and /api/health
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(health.router, prefix="/api/health", tags=["Health"], include_in_schema=False)

# Core API routes
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
