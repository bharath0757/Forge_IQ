import math
import hashlib
import re
from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np


class EmbeddingProvider(ABC):
    """Abstract interface for embedding text into dense vector representations."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string into a vector."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document chunk texts into vectors."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embeddings using OpenAI's embedding API via LangChain."""

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: Optional[str] = None):
        from langchain_openai import OpenAIEmbeddings
        kwargs = {"model": model_name}
        if api_key:
            kwargs["api_key"] = api_key
        self.client = OpenAIEmbeddings(**kwargs)

    def embed_query(self, text: str) -> List[float]:
        return self.client.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """
    Fast, deterministic embedding provider for local development, offline runs, and unit tests.
    Uses token hashing and term weighting with L2 normalization to compute dense non-negative vectors.
    """

    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def _text_to_vector(self, text: str) -> List[float]:
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = re.findall(r'\w+', text.lower())
        if not tokens:
            return vec.tolist()

        for token in tokens:
            # Deterministic token bucket
            h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.0

        # Add 2-gram representations for phrase capturing
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}_{tokens[i+1]}"
            h = int(hashlib.md5(bigram.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_query(self, text: str) -> List[float]:
        return self._text_to_vector(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]
