from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9']+")
VECTOR_DIM = 256


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _bucket(token: str, dimensions: int) -> int:
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") % dimensions


class LexicalEmbedder:
    """Deterministic bag-of-words hashing. Tests and offline retrieval; not a model embedding."""

    def __init__(self, dimensions: int = VECTOR_DIM) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            vector[_bucket(token, self.dimensions)] += 1.0
        return l2_normalize(vector)


class AsyncEmbedder(Protocol):
    async def embed(self, texts: str | Sequence[str]) -> list[list[float]]: ...


class ProviderEmbedder:
    """Adapt the async LLM provider embedding port to the memory layer."""

    def __init__(self, provider) -> None:
        self.provider = provider

    async def embed(self, texts: str | Sequence[str]) -> list[list[float]]:
        result = await self.provider.embed(texts)
        return result.embeddings


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def estimate_tokens(*texts: str) -> int:
    words = sum(len(tokenize(text)) for text in texts if text)
    return max(1, int(words * 1.3)) if words else 0
