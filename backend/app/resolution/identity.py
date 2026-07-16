"""Stable identities for canonical entities."""

from __future__ import annotations

import hashlib

from app.resolution.normalization import normalize_name


RESOLUTION_VERSION = "v1"


def canonical_id_for_name(name: str, *, entity_type: str = "") -> str:
    """Return a deterministic identity based only on the normalized name.

    ``entity_type`` is intentionally accepted but excluded from the digest:
    extraction types can drift between documents without changing identity.
    """

    del entity_type
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("name must not normalize to an empty key")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"canonical:{RESOLUTION_VERSION}:{digest}"
