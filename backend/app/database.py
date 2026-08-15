from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe schema migration for SQLite
    with engine.connect() as conn:
        for col, col_type in [("stage", "VARCHAR"), ("stages", "JSON"), ("messages", "JSON")]:
            try:
                conn.execute(text(f"ALTER TABLE processing_jobs ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass
