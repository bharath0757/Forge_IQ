from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import numpy as np
from app.retrieval.models import RetrievedEvidence


class VectorStore(ABC):
    """Abstract interface for vector database storage and similarity search."""

    @abstractmethod
    def add_documents(self, items: List[RetrievedEvidence], embeddings: List[List[float]]) -> None:
        """Store items along with their vector embeddings."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedEvidence]:
        """Perform similarity search and return top-k matching evidence items with similarity scores."""
        pass

    @abstractmethod
    def get_by_ids(self, ids: List[str]) -> List[RetrievedEvidence]:
        """Retrieve evidence items by their unique IDs."""
        pass

    @abstractmethod
    def delete_by_document(self, document_id: str) -> None:
        """Delete all indexed evidence items belonging to a specific document."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored vectors and items."""
        pass

    def count(self) -> int:
        """Return total number of items stored."""
        return 0


class LocalVectorStore(VectorStore):
    """
    Lightweight, reliable in-memory vector store using numpy for cosine similarity.
    Ideal for local development, MVP, and unit tests without external infrastructure.
    """

    def __init__(self):
        self._items: Dict[str, RetrievedEvidence] = {}
        self._embeddings: Dict[str, np.ndarray] = {}

    def count(self) -> int:
        return len(self._items)

    def add_documents(self, items: List[RetrievedEvidence], embeddings: List[List[float]]) -> None:
        if len(items) != len(embeddings):
            raise ValueError(f"Mismatch: {len(items)} items vs {len(embeddings)} embeddings")

        for item, emb in zip(items, embeddings):
            self._items[item.evidence_id] = item
            arr = np.array(emb, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
            self._embeddings[item.evidence_id] = arr

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedEvidence]:
        if not self._items:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        candidate_ids = []
        for eid, item in self._items.items():
            if filter_criteria:
                match = True
                for k, v in filter_criteria.items():
                    if k == "product_id" and item.product_id != v:
                        match = False
                        break
                    elif k == "document_id" and item.document_id != v:
                        match = False
                        break
                    elif k == "document_name" and item.document_name != v:
                        match = False
                        break
                    elif k in item.metadata and item.metadata[k] != v:
                        match = False
                        break
                if not match:
                    continue
            candidate_ids.append(eid)

        if not candidate_ids:
            return []

        # Calculate cosine similarities
        scores = []
        for eid in candidate_ids:
            emb = self._embeddings[eid]
            dot = float(np.dot(q_vec, emb))
            # Bound score between 0.0 and 1.0
            score = max(0.0, min(1.0, dot))
            scores.append((eid, score))

        # Sort by similarity score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        top_results = scores[:top_k]

        results: List[RetrievedEvidence] = []
        for eid, score in top_results:
            item = self._items[eid]
            # Return fresh instance with updated similarity score
            result_item = item.model_copy(update={"similarity_score": round(score, 4)})
            results.append(result_item)

        return results

    def get_by_ids(self, ids: List[str]) -> List[RetrievedEvidence]:
        results = []
        for eid in ids:
            if eid in self._items:
                results.append(self._items[eid].model_copy())
        return results

    def delete_by_document(self, document_id: str) -> None:
        to_delete = [eid for eid, item in self._items.items() if item.document_id == document_id]
        for eid in to_delete:
            self._items.pop(eid, None)
            self._embeddings.pop(eid, None)

    def clear(self) -> None:
        self._items.clear()
        self._embeddings.clear()
