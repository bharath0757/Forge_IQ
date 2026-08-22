from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Build engine with proper settings for each DB backend
if settings.is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

    # Enable WAL mode for SQLite — better concurrent read performance
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):  # noqa: ARG001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # PostgreSQL (or other) — no connect_args needed
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


_db_initialized = False


def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception:
            pass


def get_db():
    ensure_db_initialized()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe schema migration for SQLite — add columns if they don't exist yet
    if settings.is_sqlite:
        with engine.connect() as conn:
            # Migration for processing_jobs
            for col, col_type in [("stage", "VARCHAR"), ("stages", "JSON"), ("messages", "JSON")]:
                try:
                    conn.execute(text(f"ALTER TABLE processing_jobs ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass
            # Migration for products
            product_cols = [
                ("manufacturer", "VARCHAR"),
                ("source_brand", "VARCHAR"),
                ("candidate_brand", "VARCHAR"),
                ("manufacturer_status", "VARCHAR"),
                ("brand_status", "VARCHAR"),
                ("manufacturer_match_type", "VARCHAR"),
                ("brand_match_type", "VARCHAR"),
                ("taxonomy_dept", "VARCHAR"),
                ("taxonomy_class", "VARCHAR"),
                ("taxonomy_fine", "VARCHAR"),
                ("taxonomy_classpath", "VARCHAR"),
                ("taxonomy_confidence", "FLOAT"),
                ("taxonomy_status", "VARCHAR"),
                ("desc_short", "VARCHAR"),
                ("desc_long", "VARCHAR"),
                ("desc_invoice", "VARCHAR"),
                ("desc_mobile", "VARCHAR"),
                ("desc_retail", "VARCHAR"),
                ("desc_marketing", "VARCHAR"),
                ("delivery_state", "VARCHAR DEFAULT 'PENDING'"),
            ]
            for col, col_type in product_cols:
                try:
                    conn.execute(text(f"ALTER TABLE products ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass
