"""Contracts for provenance-carrying entity resolution decisions."""

from enum import Enum
from pydantic import AliasChoices, BaseModel, Field, model_validator


class ResolutionStatus(str, Enum):
    """Disposition of a source entity during canonicalization."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    UNRESOLVED = "unresolved"


class ResolutionMethod(str, Enum):
    """Rule or fallback that produced a resolution candidate."""

    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    FALLBACK = "fallback"


def _require_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


class ResolutionEvidence(BaseModel):
    """Explain why one source entity was mapped (or proposed) to a target."""

    source_entity_id: str = Field(
        validation_alias=AliasChoices("source_entity_id", "entity_id")
    )
    source_document_id: str = Field(
        validation_alias=AliasChoices("source_document_id", "document_id")
    )
    source_chunk_id: str = Field(
        validation_alias=AliasChoices("source_chunk_id", "chunk_id")
    )
    canonical_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "canonical_id", "target_canonical_id", "canonical_entity_id"
        )
    )
    method: ResolutionMethod
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("score", "confidence"),
    )
    reason: str

    @model_validator(mode="after")
    def _validate_provenance(self) -> "ResolutionEvidence":
        _require_text(self.source_entity_id, "source_entity_id")
        _require_text(self.source_document_id, "source_document_id")
        _require_text(self.source_chunk_id, "source_chunk_id")
        if self.canonical_id is not None:
            _require_text(self.canonical_id, "canonical_id")
        _require_text(self.reason, "reason")
        return self

    @property
    def confidence(self) -> float:
        """Compatibility name used by extraction candidates."""

        return self.score


class CanonicalEntityReference(BaseModel):
    """Stable identity plus the provenance accumulated for that identity."""

    canonical_id: str
    canonical_name: str
    entity_type: str = ""
    source_document_ids: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_reference(self) -> "CanonicalEntityReference":
        _require_text(self.canonical_id, "canonical_id")
        _require_text(self.canonical_name, "canonical_name")
        if self.entity_type:
            _require_text(self.entity_type, "entity_type")
        for field_name in ("source_document_ids", "source_chunk_ids"):
            values = getattr(self, field_name)
            for value in values:
                _require_text(value, field_name)
        return self


class AliasRecord(BaseModel):
    """A source spelling retained as an alias with its original location."""

    alias: str = Field(validation_alias=AliasChoices("alias", "alias_name", "name"))
    canonical_id: str = Field(
        validation_alias=AliasChoices(
            "canonical_id", "target_canonical_id", "canonical_entity_id"
        )
    )
    source_entity_id: str = Field(
        validation_alias=AliasChoices("source_entity_id", "entity_id")
    )
    source_document_id: str = Field(
        validation_alias=AliasChoices("source_document_id", "document_id")
    )
    source_chunk_id: str = Field(
        validation_alias=AliasChoices("source_chunk_id", "chunk_id")
    )

    @model_validator(mode="after")
    def _validate_record(self) -> "AliasRecord":
        _require_text(self.alias, "alias")
        _require_text(self.canonical_id, "canonical_id")
        _require_text(self.source_entity_id, "source_entity_id")
        _require_text(self.source_document_id, "source_document_id")
        _require_text(self.source_chunk_id, "source_chunk_id")
        return self


class ResolutionCandidate(BaseModel):
    """One source entity's resolution decision, including safe unresolved state."""

    source_entity_id: str = Field(
        validation_alias=AliasChoices("source_entity_id", "entity_id")
    )
    source_name: str = Field(validation_alias=AliasChoices("source_name", "name"))
    source_document_id: str = Field(
        validation_alias=AliasChoices("source_document_id", "document_id")
    )
    source_chunk_id: str = Field(
        validation_alias=AliasChoices("source_chunk_id", "chunk_id")
    )
    canonical_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "canonical_id", "target_canonical_id", "canonical_entity_id"
        ),
    )
    status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    method: ResolutionMethod = ResolutionMethod.FALLBACK
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("score", "confidence"),
    )
    evidence: ResolutionEvidence | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _validate_candidate(self) -> "ResolutionCandidate":
        _require_text(self.source_entity_id, "source_entity_id")
        _require_text(self.source_name, "source_name")
        _require_text(self.source_document_id, "source_document_id")
        _require_text(self.source_chunk_id, "source_chunk_id")
        if self.canonical_id is not None:
            _require_text(self.canonical_id, "canonical_id")
        if self.status is ResolutionStatus.ACCEPTED:
            if self.canonical_id is None:
                raise ValueError("accepted resolution requires canonical_id")
            if self.evidence is None:
                raise ValueError("accepted resolution requires evidence")
            if (
                self.evidence.source_entity_id != self.source_entity_id
                or self.evidence.source_document_id != self.source_document_id
                or self.evidence.source_chunk_id != self.source_chunk_id
                or self.evidence.canonical_id != self.canonical_id
            ):
                raise ValueError(
                    "accepted evidence must match candidate provenance and canonical_id"
                )
            if self.evidence.method is not self.method or self.evidence.score != self.score:
                raise ValueError("accepted evidence must match candidate method and score")
        elif self.status is ResolutionStatus.REVIEW:
            if self.evidence is None:
                raise ValueError("review resolution requires evidence")
            if (
                self.evidence.source_entity_id != self.source_entity_id
                or self.evidence.source_document_id != self.source_document_id
                or self.evidence.source_chunk_id != self.source_chunk_id
                or self.evidence.canonical_id != self.canonical_id
                or self.evidence.method is not self.method
                or self.evidence.score != self.score
            ):
                raise ValueError("review evidence must match candidate provenance, target, method, and score")
        elif self.status is ResolutionStatus.UNRESOLVED:
            if self.canonical_id is not None or self.evidence is not None:
                raise ValueError(
                    "unresolved resolution must not carry canonical_id or evidence"
                )
        return self

    @property
    def confidence(self) -> float:
        """Compatibility name used by extraction candidates."""

        return self.score


class ResolutionGroup(BaseModel):
    """Pure, write-ready view of one canonical identity and its mentions.

    ``fallback`` groups intentionally use the source entity id as their
    canonical id.  This keeps unresolved entities queryable without implying
    that a review candidate was accepted.
    """

    canonical_id: str
    canonical_name: str
    entity_type: str = ""
    source_entity_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    mention_chunk_ids: list[str] = Field(default_factory=list)
    evidence: list[ResolutionEvidence] = Field(default_factory=list)
    fallback: bool = False

    @model_validator(mode="after")
    def _validate_group(self) -> "ResolutionGroup":
        _require_text(self.canonical_id, "canonical_id")
        _require_text(self.canonical_name, "canonical_name")
        if not self.source_entity_ids:
            raise ValueError("resolution group requires source_entity_ids")
        return self


class ResolutionBatch(BaseModel):
    """Result returned by the extraction-to-resolution integration adapter."""

    candidates: list[ResolutionCandidate] = Field(default_factory=list)
    groups: list[ResolutionGroup] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)

    @property
    def resolutions(self) -> list[ResolutionCandidate]:
        """Compatibility name for callers that use ``resolutions``."""

        return self.candidates

    @property
    def canonical_groups(self) -> list[ResolutionGroup]:
        return self.groups

    @property
    def evidence(self) -> list[ResolutionEvidence]:
        return [item for group in self.groups for item in group.evidence]


# Short aliases make the adapter contract discoverable without coupling
# callers to a particular noun (batch/result/group).
ResolutionResult = ResolutionBatch
CanonicalEntityGroup = ResolutionGroup


# Short names keep callers from having to depend on the longer contract names.
CanonicalEntityRef = CanonicalEntityReference
EntityAlias = AliasRecord
ResolutionAlias = AliasRecord
