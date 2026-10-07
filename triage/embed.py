"""Embedding providers and keeping the index's vectors up to date."""

from __future__ import annotations

import os
from typing import Protocol

import numpy as np

from triage.config import EmbeddingsConfig
from triage.store import Store
from triage.text import issue_text


class SetupError(RuntimeError):
    """A provider is configured but its dependency or settings are missing."""


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


class LocalEmbedder:
    """Runs a small embedding model in-process with fastembed. Needs no API key."""

    def __init__(self, model: str):
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise SetupError("Local embeddings need the 'local' extra: uv sync --extra local") from e
        self.name = f"local:{model}"
        self._model = TextEmbedding(model_name=model)

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.array(list(self._model.embed(texts)), dtype=np.float32)


class OpenAIEmbedder:
    """Any OpenAI-compatible embeddings endpoint (OpenAI, Ollama, vLLM, hosted open-weight providers)."""

    def __init__(self, model: str, base_url: str | None = None, api_key_env: str | None = None):
        from openai import OpenAI

        self.name = f"openai:{model}"
        self._model = model
        api_key = os.environ.get(api_key_env or "OPENAI_API_KEY") or "not-needed"
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self.texts = 0
        self.tokens = 0

    def usage_summary(self) -> str:
        return f"embeddings {self.name}: {self.texts} texts, {self.tokens} tokens"

    def embed(self, texts: list[str]) -> np.ndarray:
        response = self._client.embeddings.create(model=self._model, input=texts)
        self.texts += len(texts)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.tokens += usage.prompt_tokens or 0
        return np.array([d.embedding for d in response.data], dtype=np.float32)


def make_embedder(cfg: EmbeddingsConfig) -> Embedder:
    if cfg.provider == "local":
        return LocalEmbedder(cfg.model)
    return OpenAIEmbedder(cfg.model, cfg.base_url, cfg.api_key_env)


def normalize(vectors) -> np.ndarray:
    v = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(norms == 0, 1.0, norms)


def embed_pending(store: Store, embedder: Embedder, batch_size: int = 64) -> int:
    """Embed issues that are new or changed since they were last embedded with this model."""
    pending = store.pending_embeddings(embedder.name, issue_text)
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        vectors = normalize(embedder.embed([text for _, text, _ in chunk]))
        store.save_embeddings(embedder.name, [(n, h, v) for (n, _, h), v in zip(chunk, vectors)])
        store.commit()
    return len(pending)
