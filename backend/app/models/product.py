import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, DateTime, Boolean, Table
from sqlalchemy.orm import relationship
from app.database import Base

# Association Tables
attribute_evidence = Table(
    "attribute_evidence",
    Base.metadata,
    Column("attribute_id", String, ForeignKey("product_attributes.id")),
    Column("evidence_id", String, ForeignKey("evidence.id"))
)

conflict_evidence = Table(
    "conflict_evidence",
    Base.metadata,
    Column("conflict_id", String, ForeignKey("conflicts.id")),
    Column("evidence_id", String, ForeignKey("evidence.id"))
)

conflict_sources = Table(
    "conflict_sources",
    Base.metadata,
    Column("conflict_id", String, ForeignKey("conflicts.id")),
    Column("source_id", String, ForeignKey("sources.id"))
)


class ProductTwin(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    part_number = Column(String, index=True)
    brand = Column(String, index=True)
    description = Column(String)
    category = Column(String, index=True)
    overall_quality_score = Column(Float)
    status = Column(String, index=True)
    evidence_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    attributes = relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan")
    conflicts = relationship("Conflict", back_populates="product", cascade="all, delete-orphan")
    review_decisions = relationship("ReviewDecision", back_populates="product", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="product", cascade="all, delete-orphan")


class ProductAttribute(Base):
    __tablename__ = "product_attributes"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True)
    name = Column(String, index=True)
    value = Column(JSON)
    normalized_value = Column(JSON, nullable=True)
    unit = Column(String, nullable=True)
    confidence = Column(Float)
    status = Column(String)

    product = relationship("ProductTwin", back_populates="attributes")
    evidence = relationship("Evidence", secondary=attribute_evidence, back_populates="attributes")


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    type = Column(String)
    url = Column(String, nullable=True)
    document_name = Column(String, nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True, index=True)
    source_name = Column(String)
    source_type = Column(String)
    source_url = Column(String, nullable=True)
    document_name = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    snippet = Column(String)
    extracted_text = Column(String)
    reliability_score = Column(Float)

    attributes = relationship("ProductAttribute", secondary=attribute_evidence, back_populates="evidence")
    conflicts = relationship("Conflict", secondary=conflict_evidence, back_populates="evidence")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(String, primary_key=True, index=True)
    attribute_id = Column(String, ForeignKey("product_attributes.id"), index=True)
    rule = Column(String)
    passed = Column(Boolean)
    message = Column(String)
    severity = Column(String)

    attribute = relationship("ProductAttribute", backref="validation_results")


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True)
    attribute = Column(String, index=True)
    values = Column(JSON)
    severity = Column(String)
    status = Column(String, index=True)

    product = relationship("ProductTwin", back_populates="conflicts")
    sources = relationship("Source", secondary=conflict_sources)
    evidence = relationship("Evidence", secondary=conflict_evidence, back_populates="conflicts")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True)
    attribute = Column(String, index=True)
    previous_value = Column(JSON)
    selected_value = Column(JSON)
    reviewer_action = Column(String)
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    product = relationship("ProductTwin", back_populates="review_decisions")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), index=True)
    status = Column(String)  # PENDING, RUNNING, COMPLETED, FAILED
    stage = Column(String, default="01 IDENTIFY")
    progress = Column(Integer, default=0)
    stages = Column(JSON, default=dict)
    messages = Column(JSON, default=list)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    product = relationship("ProductTwin", back_populates="processing_jobs")
