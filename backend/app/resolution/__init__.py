"""Entity-resolution contract models."""

from app.resolution.models import (
    AliasRecord,
    CanonicalEntityRef,
    CanonicalEntityReference,
    EntityAlias,
    ResolutionAlias,
    ResolutionCandidate,
    ResolutionBatch,
    ResolutionEvidence,
    ResolutionGroup,
    ResolutionMethod,
    ResolutionResult,
    ResolutionStatus,
    CanonicalEntityGroup,
)
from app.resolution.adapter import (
    ResolutionAdapter,
    adapt_merged_entities,
    resolve_entities,
    resolve_merged_entities,
)
from app.resolution.normalization import normalize_name
from app.resolution.resolver import DeterministicResolver, EntityResolver

__all__ = [
    "ResolutionStatus",
    "ResolutionMethod",
    "ResolutionEvidence",
    "ResolutionCandidate",
    "ResolutionBatch",
    "ResolutionResult",
    "ResolutionGroup",
    "CanonicalEntityGroup",
    "CanonicalEntityReference",
    "CanonicalEntityRef",
    "AliasRecord",
    "EntityAlias",
    "ResolutionAlias",
    "DeterministicResolver",
    "EntityResolver",
    "ResolutionAdapter",
    "adapt_merged_entities",
    "resolve_entities",
    "resolve_merged_entities",
    "normalize_name",
]
