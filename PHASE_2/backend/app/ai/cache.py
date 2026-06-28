"""
Narrative cache.

Public API
----------
NarrativeCache          Protocol — the interface NarrativeService depends on
InMemoryNarrativeCache  Default implementation (dict-backed, process-local)

Cache key convention
--------------------
The key is always produced by app.ai.renderer.cache_key(), which hashes
SHA-256(model_name + "::" + AdvisorInput JSON).  This means:

  - Same facts + same model  → same key → cache hit
  - Any number changes       → hash changes → cache miss (no stale narration)
  - Model upgrade            → hash changes → cache miss (no old narration)

Swapping implementations
------------------------
For a Redis/session_store-backed cache, implement the NarrativeCache Protocol
and pass an instance to NarrativeService.__init__().  NarrativeService never
imports InMemoryNarrativeCache directly; it only depends on the Protocol.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from app.engines.advisor_contract import AdvisorInput


# ---------------------------------------------------------------------------
# Cache key helper — lives here so both cache implementations and
# NarrativeService import it from the same place.
# ---------------------------------------------------------------------------


def cache_key(advisor_input: AdvisorInput, model: str) -> str:
    """
    SHA-256 of (model_name + "::" + serialised AdvisorInput JSON).

    Including the model name means upgrading ai_model naturally
    invalidates old entries — you never serve a Sonnet-4.6-era narrative
    once you've moved to a newer model, and A/B testing two versions
    against the same facts never collides.
    """
    payload = advisor_input.model_dump_json()
    combined = f"{model}::{payload}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class NarrativeCache:
    """
    Structural Protocol for the narrative cache.

    Any class that implements `async get / async set` satisfies this
    interface without needing to inherit from it — standard duck-typing.
    """

    async def get(self, key: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        ...

    async def set(self, key: str, value: Dict[str, Any]) -> None:  # pragma: no cover
        ...


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


class InMemoryNarrativeCache:
    """
    Process-local in-memory cache.  Sufficient for the hackathon;
    swap for a Redis/DragonflyDB-backed implementation in production.

    Thread safety: dict reads/writes are GIL-protected in CPython, and
    FastAPI runs async handlers on the same thread, so no lock is needed
    for the typical single-worker use case.  For multi-process deployments,
    replace with a shared-memory or external cache.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._store.get(key)

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        self._store[key] = value

    def clear(self) -> None:
        """Utility for tests — not part of the Protocol."""
        self._store.clear()

    def size(self) -> int:
        """Utility for tests / health-check — not part of the Protocol."""
        return len(self._store)
