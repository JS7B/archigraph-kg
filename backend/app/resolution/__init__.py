"""Entity-resolution contract models."""

from app.resolution.models import (
    AliasRecord,
    CanonicalEntityRef,
    CanonicalEntityReference,
    EntityAlias,
    ResolutionAlias,
    ResolutionCandidate,
    ResolutionEvidence,
    ResolutionMethod,
    ResolutionStatus,
)
from app.resolution.normalization import normalize_name
from app.resolution.resolver import DeterministicResolver, EntityResolver

__all__ = [
    "ResolutionStatus",
    "ResolutionMethod",
    "ResolutionEvidence",
    "ResolutionCandidate",
    "CanonicalEntityReference",
    "CanonicalEntityRef",
    "AliasRecord",
    "EntityAlias",
    "ResolutionAlias",
    "DeterministicResolver",
    "EntityResolver",
    "normalize_name",
]
