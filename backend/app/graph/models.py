"""Response contracts for source and canonical graph exploration endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


class _GraphResponseModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class GraphEvidence(_GraphResponseModel):
    """A source chunk reference kept alongside graph facts."""

    chunk_id: str
    document_id: str | None = None


EvidenceReference = GraphEvidence


class GraphNode(_GraphResponseModel):
    id: str
    name: str
    type: str
    document_id: str
    degree: int | None = None
    mention_count: int | None = None


class GraphEdge(_GraphResponseModel):
    source: str
    target: str
    type: str
    confidence: float | None = None
    evidence_chunk_id: str | None = None
    evidence: GraphEvidence | None = None


class LocalSubgraphMetadata(_GraphResponseModel):
    depth: int
    limit: int
    node_count: int
    edge_count: int
    truncated: bool


class LocalSubgraphResponse(_GraphResponseModel):
    center_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: LocalSubgraphMetadata


class CanonicalGraphEvidence(_GraphResponseModel):
    """One real source relation fact supporting an aggregated canonical edge."""

    chunk_id: str
    document_id: str
    source_entity_id: str
    target_entity_id: str
    confidence: float | None = None


class CanonicalGraphNode(_GraphResponseModel):
    """A canonical identity with source-derived, deletion-safe display metadata."""

    id: str
    name: str
    type: str
    identity: Literal["canonical"] = "canonical"
    document_ids: list[str] = Field(default_factory=list)
    source_entity_count: int = Field(ge=0)
    mention_count: int = Field(ge=0)
    aliases: list[str] = Field(default_factory=list)
    alias_count: int = Field(ge=0)
    aliases_truncated: bool = False
    degree: int = Field(default=0, ge=0)


class CanonicalGraphEdge(_GraphResponseModel):
    """A directed relation key aggregated from eligible source facts."""

    id: str
    source: str
    target: str
    type: str
    confidence: float | None = None
    support_count: int = Field(ge=1)
    evidence_count: int = Field(ge=1)
    evidence: list[CanonicalGraphEvidence] = Field(default_factory=list)
    evidence_truncated: bool = False


class ProjectionCoverage(_GraphResponseModel):
    """Explain which source facts are visible in the accepted canonical graph."""

    source_entity_count: int = Field(ge=0)
    accepted_source_entity_count: int = Field(ge=0)
    review_source_entity_count: int = Field(ge=0)
    unresolved_source_entity_count: int = Field(ge=0)
    source_relation_count: int = Field(ge=0)
    projected_source_relation_count: int = Field(ge=0)
    excluded_relation_count: int = Field(ge=0)
    collapsed_self_relation_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _relation_partition_is_complete(self) -> "ProjectionCoverage":
        classified = (
            self.projected_source_relation_count
            + self.excluded_relation_count
            + self.collapsed_self_relation_count
        )
        if classified != self.source_relation_count:
            raise ValueError(
                "source_relation_count must equal projected + excluded + collapsed self"
            )
        return self


class CanonicalCommunity(_GraphResponseModel):
    id: str
    representative_node: CanonicalGraphNode
    node_count: int = Field(ge=1)
    edge_count: int = Field(ge=0)
    total_support: int = Field(ge=0)
    document_ids: list[str] = Field(default_factory=list)


class CanonicalCommunityMetadata(_GraphResponseModel):
    limit: int
    node_limit: int
    edge_limit: int
    evidence_limit: int
    community_count: int = Field(ge=0)
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    truncated: bool


class CanonicalCommunityResponse(_GraphResponseModel):
    communities: list[CanonicalCommunity]
    coverage: ProjectionCoverage
    metadata: CanonicalCommunityMetadata


class CanonicalSubgraphMetadata(_GraphResponseModel):
    depth: int
    node_limit: int
    edge_limit: int
    evidence_limit: int
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    truncated: bool


class CanonicalSubgraphResponse(_GraphResponseModel):
    center_id: str
    nodes: list[CanonicalGraphNode]
    edges: list[CanonicalGraphEdge]
    coverage: ProjectionCoverage
    metadata: CanonicalSubgraphMetadata


class ProjectionSnapshot(BaseModel):
    """Internal bounded projection shared by communities and local traversal."""

    nodes: list[CanonicalGraphNode]
    edges: list[CanonicalGraphEdge]
    coverage: ProjectionCoverage
    total_node_count: int = Field(ge=0)
    total_edge_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    node_truncated: bool = False
    edge_truncated: bool = False
    evidence_truncated: bool = False

    @property
    def truncated(self) -> bool:
        return self.node_truncated or self.edge_truncated or self.evidence_truncated


class BoundedProjection(BaseModel):
    nodes: list[CanonicalGraphNode]
    edges: list[CanonicalGraphEdge]
    truncated: bool = False
