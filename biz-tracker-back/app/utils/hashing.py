"""Small hashing utilities."""
from __future__ import annotations

import hashlib


def sha256_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
