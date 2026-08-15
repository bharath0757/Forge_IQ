# cspell:ignore ondelete primaryjoin
import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # PDF, IMAGE, etc.
    file_size = Column(Integer)
    page_count = Column(Integer, default=0)
    status = Column(String, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = Column(String, nullable=True)
    product_id = Column(String, nullable=True)  # optional link to a product
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_name = Column(String, nullable=False)
    page_number = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    source_type = Column(String, nullable=False)  # PDF, IMAGE, etc.
    char_count = Column(Integer, default=0)

    document = relationship("Document", back_populates="chunks",
                            foreign_keys=[document_id],
                            primaryjoin="DocumentChunk.document_id == Document.id")
