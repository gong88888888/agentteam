"""Embedding backends: local bge-m3 via Ollama, deterministic hashing fallback."""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

import requests

from .chunker import tokenize


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic feature hashing; no network, used for CI and fallback."""
    name = "hash:256"
    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in tokenize(text):
                h = int.from_bytes(hashlib.blake2b(tok.encode("utf-8"),
                                                   digest_size=4).digest(), "big")
                idx = h % self.dim
                sign = 1.0 if (h >> 31) & 1 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class OllamaEmbedder:
    name = "ollama:bge-m3:latest"
    dim = 1024

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "bge-m3:latest", timeout_s: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=4)
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
            return self.model in names
        except requests.RequestException:
            return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 16):
            batch = texts[i:i + 16]
            r = requests.post(f"{self.base_url}/api/embed",
                              json={"model": self.model, "input": batch},
                              timeout=(5, self.timeout_s))
            r.raise_for_status()
            vectors = r.json().get("embeddings") or []
            if len(vectors) != len(batch):
                raise RuntimeError("Ollama embeddings 数量不匹配")
            out.extend(vectors)
        if out:
            self.dim = len(out[0])
        return out


def get_embedder(cfg: dict | None = None, backend: str = "auto") -> Embedder:
    if backend == "hash":
        return HashingEmbedder()
    local = (cfg or {}).get("models", {}).get("local", {})
    ollama = OllamaEmbedder(local.get("base_url", "http://localhost:11434"))
    if backend == "ollama" or (backend == "auto" and ollama.available()):
        return ollama
    return HashingEmbedder()


def embedder_from_name(name: str, cfg: dict | None = None) -> Embedder:
    if name.startswith("ollama:"):
        local = (cfg or {}).get("models", {}).get("local", {})
        return OllamaEmbedder(local.get("base_url", "http://localhost:11434"),
                              name.split(":", 1)[1])
    return HashingEmbedder()
