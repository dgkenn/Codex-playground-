"""Content hashing -- every persisted artifact carries a verifiable SHA-256.

The firewall (Sec 3) requires that four objects be *frozen and hash-verified*
before the held-out data is unlocked: the model checkpoint, the harmonization
config, the embedding-correction transform, and the phenotype-assignment
function. These helpers produce stable, canonical hashes for files, byte blobs,
and (crucially) JSON-serialisable Python objects so configs and learned
transforms can be pinned reproducibly.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

_CHUNK = 1 << 20  # 1 MiB streaming reads -- never load a whole file into RAM


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | os.PathLike) -> str:
    """Stream a file through SHA-256 (disk-sparing: constant memory)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON encoding: sorted keys, no insignificant whitespace.

    Two semantically-equal configs always serialise to identical bytes, so their
    hashes match regardless of key order or formatting.
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def hash_object(obj: Any) -> str:
    """Canonical-JSON content hash of any JSON-serialisable object."""
    return hash_bytes(canonical_json(obj))


def short(h: str, n: int = 12) -> str:
    return h[:n]


def verify(path_or_obj: Any, expected: str, *, is_file: bool = False) -> bool:
    """Return True iff the content hash matches `expected` (case-insensitive)."""
    actual = hash_file(path_or_obj) if is_file else hash_object(path_or_obj)
    return actual.lower() == str(expected).lower()
