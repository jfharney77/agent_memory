"""Thin Ollama client: chat, JSON-mode chat, and embeddings.

Kept dependency-free on purpose. The point of this project is the memory
plumbing, not the model wrapper.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import requests

from . import config


class OllamaError(RuntimeError):
    pass


def _post(path: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    url = f"{config.OLLAMA_BASE_URL}{path}"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(
            f"Could not reach Ollama at {url}. "
            f"Check OLLAMA_BASE_URL in .env (from WSL the Windows host is usually "
            f"the nameserver in /etc/resolv.conf). Original error: {exc}"
        ) from exc
    return resp.json()


def chat(messages: list[dict[str, str]], temperature: float = 0.3) -> str:
    """Plain chat completion."""
    data = _post(
        "/api/chat",
        {
            "model": config.CHAT_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    return data["message"]["content"].strip()


def chat_json(messages: list[dict[str, str]], temperature: float = 0.0) -> Any:
    """Chat completion constrained to JSON. Returns None if the model wanders."""
    data = _post(
        "/api/chat",
        {
            "model": config.CHAT_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        },
    )
    raw = data["message"]["content"].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def embed(text: str) -> np.ndarray:
    """Unit-normalised embedding, so cosine similarity is a plain dot product."""
    data = _post("/api/embed", {"model": config.EMBED_MODEL, "input": text})
    vec = np.asarray(data["embeddings"][0], dtype=np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def embed_many(texts: list[str]) -> list[np.ndarray]:
    if not texts:
        return []
    data = _post("/api/embed", {"model": config.EMBED_MODEL, "input": texts})
    out = []
    for row in data["embeddings"]:
        vec = np.asarray(row, dtype=np.float32)
        norm = np.linalg.norm(vec)
        out.append(vec / norm if norm else vec)
    return out
