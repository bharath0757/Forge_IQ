import uuid
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from app.retrieval.models import RetrievedEvidence
from app.retrieval.embeddings import (
    EmbeddingProvider,
    DeterministicEmbeddingProvider,
    NVIDIAEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.retrieval.vector_store import VectorStore, LocalVectorStore
from app.config import settings

logger = logging.getLogger(__name__)


class BaseEvidenceRetriever(ABC):
    """Abstract interface for evidence indexing, search, and retrieval."""

    @abstractmethod
    def index_document(
        self,
        document_id: str,
        document_name: str,
        chunks: List[Any],
        product_id: Optional[str] = None
    ) -> List[str]:
        """
        Index chunks of a document into vector storage.
        Returns the list of indexed evidence IDs.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedEvidence]:
        """
        Perform similarity search on indexed evidence given a text query.
        Returns top-k matching evidence items preserving document, page, chunk, text, and similarity_score.
        """
        pass

    @abstractmethod
    def get_evidence(self, evidence_ids: List[str]) -> List[RetrievedEvidence]:
        """
        Retrieve specific evidence records by their IDs.
        """
        pass


class EvidenceRetriever(BaseEvidenceRetriever):
    """
    Evidence retrieval engine for ForgeIQ.
    Coordinates embedding generation, vector storage, and similarity retrieval.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.vector_store = vector_store or LocalVectorStore()
        
        if embedding_provider is not None:
            self.embedding_provider = embedding_provider
        elif settings.ai_provider == "nvidia":
            self.embedding_provider = NVIDIAEmbeddingProvider()
        elif settings.openai_api_key:
            self.embedding_provider = OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
        else:
            self.embedding_provider = DeterministicEmbeddingProvider()

    def index_document(
        self,
        document_id: str,
        document_name: str,
        chunks: List[Any],
        product_id: Optional[str] = None
    ) -> List[str]:
        if not chunks:
            logger.info(f"No chunks to index for document {document_id}")
            return []

        evidence_items: List[RetrievedEvidence] = []
        texts: List[str] = []

        for idx, chunk in enumerate(chunks):
            # Extract attributes from various chunk representations (ExtractedChunk, DocumentChunk, dict, etc.)
            page_number = getattr(chunk, "page_number", None)
            chunk_index = getattr(chunk, "chunk_index", idx)
            text = getattr(chunk, "text", "")
            chunk_id = getattr(chunk, "id", None)

            if isinstance(chunk, dict):
                page_number = chunk.get("page_number")
                chunk_index = chunk.get("chunk_index", idx)
                text = chunk.get("text", "")
                chunk_id = chunk.get("id")

            if not text or not text.strip():
                continue

            evidence_id = chunk_id or f"ev_{document_id}_p{page_number or 1}_c{chunk_index}_{uuid.uuid4().hex[:6]}"

            evidence_item = RetrievedEvidence(
                evidence_id=evidence_id,
                document_id=document_id,
                document_name=document_name,
                page_number=page_number,
                chunk_index=chunk_index,
                text=text.strip(),
                similarity_score=0.0,
                product_id=product_id,
                metadata={
                    "char_count": len(text.strip()),
                }
            )
            evidence_items.append(evidence_item)
            texts.append(evidence_item.text)

        if not evidence_items:
            return []

        # Generate embeddings in batch
        embeddings = self.embedding_provider.embed_documents(texts)

        # Store in vector database
        self.vector_store.add_documents(evidence_items, embeddings)
        logger.info(f"Indexed {len(evidence_items)} chunks for document '{document_name}' (ID: {document_id})")

        return [item.evidence_id for item in evidence_items]

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedEvidence]:
        if not query or not query.strip():
            return []

        query_embedding = self.embedding_provider.embed_query(query.strip())
        return self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_criteria=filter_criteria
        )

    def get_evidence(self, evidence_ids: List[str]) -> List[RetrievedEvidence]:
        if not evidence_ids:
            return []
        return self.vector_store.get_by_ids(evidence_ids)


# Global singleton instance for application use
_default_retriever: Optional[EvidenceRetriever] = None


def get_evidence_retriever() -> EvidenceRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = EvidenceRetriever()
    return _default_retriever


def set_evidence_retriever(retriever: EvidenceRetriever) -> None:
    global _default_retriever
    _default_retriever = retriever
