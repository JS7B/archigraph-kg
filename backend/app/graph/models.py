"""Response contracts for bounded graph exploration endpoints."""

from pydantic import BaseModel, ConfigDict, Field


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
