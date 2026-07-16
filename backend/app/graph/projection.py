"""Pure helpers and Neo4j reads for the accepted canonical graph projection.

The projection is deliberately read-only: source ``RELATES`` facts remain the
authoritative records and are grouped by their accepted canonical endpoints at
query time.  Alias reassignment and document deletion therefore take effect
without maintaining a second materialized relationship layer.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from neo4j import Driver

from app.graph.models import (
    BoundedProjection,
    CanonicalCommunity,
    CanonicalGraphEdge,
    CanonicalGraphEvidence,
    CanonicalGraphNode,
    ProjectionCoverage,
    ProjectionSnapshot,
)


def _digest(prefix: str, parts: Sequence[str]) -> str:
    payload = json.dumps(
        list(parts), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"{prefix}{hashlib.sha256(payload).hexdigest()}"


def canonical_edge_id(source: str, target: str, relation_type: str) -> str:
    """Return a stable ID for one complete directed canonical relation key."""

    return _digest("canonical-edge:v1:", (source, target, relation_type))


def community_id(member_ids: Iterable[str]) -> str:
    """Return a stable ID for one exact canonical membership set."""

    return _digest("community:v1:", tuple(sorted(set(member_ids))))


def _row_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "data"):
        return dict(row.data())
    return dict(row)


def _evidence_key(item: CanonicalGraphEvidence) -> tuple:
    return (
        item.document_id,
        item.chunk_id,
        item.source_entity_id,
        item.target_entity_id,
        -1.0 if item.confidence is None else item.confidence,
    )


def aggregate_projection(
    node_rows: Iterable[Mapping[str, Any]],
    fact_rows: Iterable[Mapping[str, Any]],
    coverage: ProjectionCoverage | Mapping[str, Any],
    *,
    node_limit: int,
    edge_limit: int,
    evidence_limit: int,
    alias_limit: int = 20,
    preferred_node_id: str | None = None,
) -> ProjectionSnapshot:
    """Build a stable, bounded projection from already eligibility-filtered rows."""

    coverage_model = ProjectionCoverage.model_validate(coverage)
    raw_nodes = sorted(
        (_row_dict(row) for row in node_rows),
        key=lambda row: (
            row["canonical_id"] != preferred_node_id
            if preferred_node_id is not None
            else False,
            row["canonical_id"],
        ),
    )
    total_node_count = len(raw_nodes)
    selected_rows = raw_nodes[:node_limit]
    selected_ids = {row["canonical_id"] for row in selected_rows}

    normalized_fact_rows = [_row_dict(row) for row in fact_rows]
    grouped: dict[tuple[str, str, str], dict[tuple, CanonicalGraphEvidence]] = {}
    aggregate_edges: list[CanonicalGraphEdge] = []
    for raw in normalized_fact_rows:
        source = raw["source_canonical_id"]
        target = raw["target_canonical_id"]
        if source == target or source not in selected_ids or target not in selected_ids:
            continue
        relation_type = raw.get("type") or ""
        if "evidence" in raw:
            evidence_all = sorted(
                (
                    CanonicalGraphEvidence.model_validate(item)
                    for item in (raw.get("evidence") or [])
                ),
                key=_evidence_key,
            )
            evidence_count = int(raw.get("evidence_count") or len(evidence_all))
            aggregate_edges.append(
                CanonicalGraphEdge(
                    id=canonical_edge_id(source, target, relation_type),
                    source=source,
                    target=target,
                    type=relation_type,
                    confidence=raw.get("confidence"),
                    support_count=int(
                        raw.get("support_count") or evidence_count
                    ),
                    evidence_count=evidence_count,
                    evidence=evidence_all[:evidence_limit],
                    evidence_truncated=(
                        evidence_count > min(len(evidence_all), evidence_limit)
                    ),
                )
            )
            continue
        key = (source, target, relation_type)
        evidence = CanonicalGraphEvidence(
            chunk_id=raw["chunk_id"],
            document_id=raw["document_id"],
            source_entity_id=raw["source_entity_id"],
            target_entity_id=raw["target_entity_id"],
            confidence=raw.get("confidence"),
        )
        grouped.setdefault(key, {})[_evidence_key(evidence)] = evidence

    complete_edges: list[CanonicalGraphEdge] = aggregate_edges
    for key, evidence_by_key in grouped.items():
        source, target, relation_type = key
        evidence_all = sorted(evidence_by_key.values(), key=_evidence_key)
        confidences = [
            item.confidence for item in evidence_all if item.confidence is not None
        ]
        complete_edges.append(
            CanonicalGraphEdge(
                id=canonical_edge_id(source, target, relation_type),
                source=source,
                target=target,
                type=relation_type,
                confidence=max(confidences) if confidences else None,
                support_count=len(evidence_all),
                evidence_count=len(evidence_all),
                evidence=evidence_all[:evidence_limit],
                evidence_truncated=len(evidence_all) > evidence_limit,
            )
        )
    complete_edges.sort(key=lambda edge: (-edge.support_count, edge.id))
    total_edge_count = len(complete_edges)
    edges = complete_edges[:edge_limit]

    degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        degree[edge.source] += 1
        degree[edge.target] += 1

    nodes: list[CanonicalGraphNode] = []
    for raw in selected_rows:
        aliases = sorted(
            {
                str(value)
                for value in (raw.get("source_names") or [])
                if value is not None and str(value).strip()
            }
        )
        documents = sorted(
            {
                str(value)
                for value in (raw.get("document_ids") or [])
                if value is not None and str(value).strip()
            }
        )
        canonical_id = raw["canonical_id"]
        nodes.append(
            CanonicalGraphNode(
                id=canonical_id,
                name=raw.get("canonical_name") or "",
                type=raw.get("entity_type") or "",
                document_ids=documents,
                source_entity_count=int(raw.get("source_entity_count") or 0),
                mention_count=int(raw.get("mention_count") or 0),
                aliases=aliases[:alias_limit],
                alias_count=len(aliases),
                aliases_truncated=len(aliases) > alias_limit,
                degree=degree[canonical_id],
            )
        )

    evidence_count = sum(edge.evidence_count for edge in edges)
    return ProjectionSnapshot(
        nodes=nodes,
        edges=edges,
        coverage=coverage_model,
        total_node_count=total_node_count,
        total_edge_count=total_edge_count,
        evidence_count=evidence_count,
        node_truncated=total_node_count > node_limit,
        edge_truncated=total_edge_count > edge_limit,
        evidence_truncated=any(edge.evidence_truncated for edge in edges),
    )


_COVERAGE_QUERY = """
/* canonical_coverage */
CALL () {
  MATCH (source:Entity)
  WHERE $document_id IS NULL OR source.document_id = $document_id
  RETURN count(source) AS source_entity_count
}
CALL () {
  MATCH (source:Entity)-[resolution:RESOLVES_TO]->(:CanonicalEntity)
  WHERE ($document_id IS NULL OR source.document_id = $document_id)
    AND resolution.source_document_id = source.document_id
    AND EXISTS {
      MATCH (document:Document {document_id: source.document_id})
            -[:HAS_CHUNK]->(evidence:Chunk {
              chunk_id: resolution.evidence_chunk_id
            })-[:MENTIONS]->(source)
      WHERE evidence.document_id = source.document_id
    }
  RETURN count(DISTINCT source) AS accepted_source_entity_count
}
CALL () {
  MATCH (source:Entity)
  WHERE ($document_id IS NULL OR source.document_id = $document_id)
    AND source.resolution_status = 'review'
  RETURN count(source) AS review_source_entity_count
}
CALL () {
  MATCH (source:Entity)
  WHERE ($document_id IS NULL OR source.document_id = $document_id)
    AND source.resolution_status = 'unresolved'
  RETURN count(source) AS unresolved_source_entity_count
}
CALL () {
  MATCH (source:Entity)-[relation:RELATES]->(:Entity)
  WHERE $document_id IS NULL OR source.document_id = $document_id
  RETURN count(relation) AS source_relation_count
}
CALL () {
  MATCH (source:Entity)-[source_resolution:RESOLVES_TO]
        ->(source_canonical:CanonicalEntity)
  MATCH (source)-[relation:RELATES]->(target:Entity)
  MATCH (target)-[target_resolution:RESOLVES_TO]
        ->(target_canonical:CanonicalEntity)
  WHERE ($document_id IS NULL OR source.document_id = $document_id)
    AND source.document_id = target.document_id
    AND coalesce(relation.confidence, 0.0) >= $min_confidence
    AND source_resolution.source_document_id = source.document_id
    AND target_resolution.source_document_id = target.document_id
    AND EXISTS {
      MATCH (source_document:Document {document_id: source.document_id})
            -[:HAS_CHUNK]->(source_evidence:Chunk {
              chunk_id: source_resolution.evidence_chunk_id
            })-[:MENTIONS]->(source)
      WHERE source_evidence.document_id = source.document_id
    }
    AND EXISTS {
      MATCH (target_document:Document {document_id: target.document_id})
            -[:HAS_CHUNK]->(target_evidence:Chunk {
              chunk_id: target_resolution.evidence_chunk_id
            })-[:MENTIONS]->(target)
      WHERE target_evidence.document_id = target.document_id
    }
    AND EXISTS {
      MATCH (relation_document:Document {document_id: source.document_id})
            -[:HAS_CHUNK]->(relation_evidence:Chunk {
              chunk_id: relation.evidence_chunk_id
            })
      WHERE relation_evidence.document_id = source.document_id
        AND EXISTS { MATCH (relation_evidence)-[:MENTIONS]->(source) }
        AND EXISTS { MATCH (relation_evidence)-[:MENTIONS]->(target) }
    }
  RETURN count(relation) AS eligible_relation_count,
         sum(CASE
           WHEN source_canonical.canonical_id = target_canonical.canonical_id
           THEN 1 ELSE 0
         END) AS collapsed_self_relation_count
}
WITH source_entity_count,
     accepted_source_entity_count,
     review_source_entity_count,
     unresolved_source_entity_count,
     source_relation_count,
     eligible_relation_count,
     coalesce(collapsed_self_relation_count, 0) AS collapsed_self_relation_count
RETURN source_entity_count,
       accepted_source_entity_count,
       review_source_entity_count,
       unresolved_source_entity_count,
       source_relation_count,
       eligible_relation_count - collapsed_self_relation_count
         AS projected_source_relation_count,
       source_relation_count - eligible_relation_count AS excluded_relation_count,
       collapsed_self_relation_count
"""


_NODES_QUERY = """
/* canonical_nodes */
MATCH (source:Entity)-[resolution:RESOLVES_TO]->(canonical:CanonicalEntity)
WHERE ($document_id IS NULL OR source.document_id = $document_id)
  AND resolution.source_document_id = source.document_id
  AND EXISTS {
    MATCH (document:Document {document_id: source.document_id})
          -[:HAS_CHUNK]->(evidence:Chunk {
            chunk_id: resolution.evidence_chunk_id
          })-[:MENTIONS]->(source)
    WHERE evidence.document_id = source.document_id
  }
WITH canonical, source
ORDER BY canonical.canonical_id, source.entity_id
WITH canonical,
     collect(DISTINCT source.document_id) AS document_ids,
     collect(DISTINCT source.name) AS source_names,
     count(DISTINCT source) AS source_entity_count,
     sum(coalesce(source.mention_count, 0)) AS mention_count
RETURN canonical.canonical_id AS canonical_id,
       canonical.canonical_name AS canonical_name,
       coalesce(canonical.entity_type, '') AS entity_type,
       document_ids,
       source_names,
       source_entity_count,
       mention_count
ORDER BY CASE WHEN canonical.canonical_id = $center_id THEN 0 ELSE 1 END,
         canonical.canonical_id
LIMIT $probe_limit
"""


_FACTS_QUERY = """
/* canonical_facts */
MATCH (source:Entity)-[source_resolution:RESOLVES_TO]
      ->(source_canonical:CanonicalEntity)
MATCH (source)-[relation:RELATES]->(target:Entity)
MATCH (target)-[target_resolution:RESOLVES_TO]
      ->(target_canonical:CanonicalEntity)
WHERE source_canonical.canonical_id IN $canonical_ids
  AND target_canonical.canonical_id IN $canonical_ids
  AND source_canonical.canonical_id <> target_canonical.canonical_id
  AND ($document_id IS NULL OR source.document_id = $document_id)
  AND source.document_id = target.document_id
  AND coalesce(relation.confidence, 0.0) >= $min_confidence
  AND source_resolution.source_document_id = source.document_id
  AND target_resolution.source_document_id = target.document_id
  AND EXISTS {
    MATCH (source_document:Document {document_id: source.document_id})
          -[:HAS_CHUNK]->(source_evidence:Chunk {
            chunk_id: source_resolution.evidence_chunk_id
          })-[:MENTIONS]->(source)
    WHERE source_evidence.document_id = source.document_id
  }
  AND EXISTS {
    MATCH (target_document:Document {document_id: target.document_id})
          -[:HAS_CHUNK]->(target_evidence:Chunk {
            chunk_id: target_resolution.evidence_chunk_id
          })-[:MENTIONS]->(target)
    WHERE target_evidence.document_id = target.document_id
  }
  AND EXISTS {
    MATCH (relation_document:Document {document_id: source.document_id})
          -[:HAS_CHUNK]->(relation_evidence:Chunk {
            chunk_id: relation.evidence_chunk_id
          })
    WHERE relation_evidence.document_id = source.document_id
      AND EXISTS { MATCH (relation_evidence)-[:MENTIONS]->(source) }
      AND EXISTS { MATCH (relation_evidence)-[:MENTIONS]->(target) }
  }
WITH source_canonical.canonical_id AS source_canonical_id,
     target_canonical.canonical_id AS target_canonical_id,
     relation.type AS type,
     relation.confidence AS confidence,
     source.document_id AS document_id,
     relation.evidence_chunk_id AS chunk_id,
     source.entity_id AS source_entity_id,
     target.entity_id AS target_entity_id
ORDER BY source_canonical_id, target_canonical_id, type,
         document_id, chunk_id, source_entity_id, target_entity_id
WITH source_canonical_id, target_canonical_id, type,
     max(confidence) AS confidence,
     collect({
       chunk_id: chunk_id,
       document_id: document_id,
       source_entity_id: source_entity_id,
       target_entity_id: target_entity_id,
       confidence: confidence
     }) AS all_evidence
RETURN source_canonical_id,
       target_canonical_id,
       type,
       confidence,
       size(all_evidence) AS support_count,
       size(all_evidence) AS evidence_count,
       all_evidence[0..$evidence_limit] AS evidence
ORDER BY support_count DESC, source_canonical_id, target_canonical_id, type
LIMIT $edge_probe_limit
"""


_SEARCH_QUERY = """
/* canonical_search */
MATCH (source:Entity)-[resolution:RESOLVES_TO]->(canonical:CanonicalEntity)
WHERE ($document_id IS NULL OR source.document_id = $document_id)
  AND resolution.source_document_id = source.document_id
  AND EXISTS {
    MATCH (document:Document {document_id: source.document_id})
          -[:HAS_CHUNK]->(evidence:Chunk {
            chunk_id: resolution.evidence_chunk_id
          })-[:MENTIONS]->(source)
    WHERE evidence.document_id = source.document_id
  }
WITH canonical, source
ORDER BY canonical.canonical_id, source.entity_id
WITH canonical,
     collect(DISTINCT source.document_id) AS document_ids,
     collect(DISTINCT source.name) AS source_names,
     count(DISTINCT source) AS source_entity_count,
     sum(coalesce(source.mention_count, 0)) AS mention_count
WHERE toLower(canonical.canonical_name) CONTAINS toLower($q)
   OR any(source_name IN source_names
          WHERE toLower(source_name) CONTAINS toLower($q))
RETURN canonical.canonical_id AS canonical_id,
       canonical.canonical_name AS canonical_name,
       coalesce(canonical.entity_type, '') AS entity_type,
       document_ids,
       source_names,
       source_entity_count,
       mention_count
ORDER BY canonical.canonical_id
LIMIT $probe_limit
"""


_DEGREES_QUERY = """
/* canonical_degrees */
MATCH (source:Entity)-[source_resolution:RESOLVES_TO]
      ->(source_canonical:CanonicalEntity)
MATCH (source)-[relation:RELATES]->(target:Entity)
MATCH (target)-[target_resolution:RESOLVES_TO]
      ->(target_canonical:CanonicalEntity)
WHERE (source_canonical.canonical_id IN $canonical_ids
       OR target_canonical.canonical_id IN $canonical_ids)
  AND source_canonical.canonical_id <> target_canonical.canonical_id
  AND ($document_id IS NULL OR source.document_id = $document_id)
  AND source.document_id = target.document_id
  AND coalesce(relation.confidence, 0.0) >= $min_confidence
  AND source_resolution.source_document_id = source.document_id
  AND target_resolution.source_document_id = target.document_id
  AND EXISTS {
    MATCH (source_document:Document {document_id: source.document_id})
          -[:HAS_CHUNK]->(source_evidence:Chunk {
            chunk_id: source_resolution.evidence_chunk_id
          })-[:MENTIONS]->(source)
    WHERE source_evidence.document_id = source.document_id
  }
  AND EXISTS {
    MATCH (target_document:Document {document_id: target.document_id})
          -[:HAS_CHUNK]->(target_evidence:Chunk {
            chunk_id: target_resolution.evidence_chunk_id
          })-[:MENTIONS]->(target)
    WHERE target_evidence.document_id = target.document_id
  }
  AND EXISTS {
    MATCH (relation_document:Document {document_id: source.document_id})
          -[:HAS_CHUNK]->(relation_evidence:Chunk {
            chunk_id: relation.evidence_chunk_id
          })
    WHERE relation_evidence.document_id = source.document_id
      AND EXISTS { MATCH (relation_evidence)-[:MENTIONS]->(source) }
      AND EXISTS { MATCH (relation_evidence)-[:MENTIONS]->(target) }
  }
WITH DISTINCT source_canonical.canonical_id AS source_canonical_id,
     target_canonical.canonical_id AS target_canonical_id,
     relation.type AS type
UNWIND [source_canonical_id, target_canonical_id] AS canonical_id
WITH canonical_id, count(*) AS degree
WHERE canonical_id IN $canonical_ids
RETURN canonical_id, degree
ORDER BY canonical_id
"""


_ZERO_COVERAGE = ProjectionCoverage(
    source_entity_count=0,
    accepted_source_entity_count=0,
    review_source_entity_count=0,
    unresolved_source_entity_count=0,
    source_relation_count=0,
    projected_source_relation_count=0,
    excluded_relation_count=0,
    collapsed_self_relation_count=0,
)


class CanonicalProjectionStore:
    """Bounded, read-only Neo4j access for canonical graph exploration."""

    def __init__(self, driver: Driver, *, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def _execute(self, query: str, **params):
        return self.driver.execute_query(
            query, **params, database_=self.database
        )[0]

    def load_coverage(
        self,
        *,
        document_id: str | None,
        min_confidence: float,
    ) -> ProjectionCoverage:
        records = list(
            self._execute(
                _COVERAGE_QUERY,
                document_id=document_id,
                min_confidence=min_confidence,
            )
        )
        if not records:
            return _ZERO_COVERAGE
        return ProjectionCoverage.model_validate(_row_dict(records[0]))

    def load_snapshot(
        self,
        *,
        node_limit: int,
        edge_limit: int,
        evidence_limit: int,
        document_id: str | None,
        min_confidence: float,
        center_id: str | None = None,
    ) -> ProjectionSnapshot:
        coverage = self.load_coverage(
            document_id=document_id, min_confidence=min_confidence
        )
        node_records = list(
            self._execute(
                _NODES_QUERY,
                document_id=document_id,
                center_id=center_id,
                probe_limit=node_limit + 1,
            )
        )
        node_rows = [_row_dict(record) for record in node_records]
        selected_ids = [
            row["canonical_id"] for row in node_rows[:node_limit]
        ]
        fact_rows: list[dict] = []
        if selected_ids:
            fact_records = self._execute(
                _FACTS_QUERY,
                canonical_ids=selected_ids,
                document_id=document_id,
                min_confidence=min_confidence,
                evidence_limit=evidence_limit,
                edge_probe_limit=edge_limit + 1,
            )
            fact_rows = [_row_dict(record) for record in fact_records]
        return aggregate_projection(
            node_rows,
            fact_rows,
            coverage,
            node_limit=node_limit,
            edge_limit=edge_limit,
            evidence_limit=evidence_limit,
            preferred_node_id=center_id,
        )

    def search(
        self,
        query: str,
        *,
        limit: int,
        document_id: str | None,
    ) -> list[CanonicalGraphNode]:
        records = self._execute(
            _SEARCH_QUERY,
            q=query,
            document_id=document_id,
            probe_limit=limit,
        )
        snapshot = aggregate_projection(
            (_row_dict(record) for record in records),
            (),
            _ZERO_COVERAGE,
            node_limit=limit,
            edge_limit=1,
            evidence_limit=1,
        )
        if not snapshot.nodes:
            return []
        degree_records = self._execute(
            _DEGREES_QUERY,
            canonical_ids=[node.id for node in snapshot.nodes],
            document_id=document_id,
            min_confidence=0.5,
        )
        degree_by_id = {
            record["canonical_id"]: int(record["degree"])
            for record in degree_records
        }
        return [
            node.model_copy(update={"degree": degree_by_id.get(node.id, 0)})
            for node in snapshot.nodes
        ]


def bounded_bfs(
    snapshot: ProjectionSnapshot,
    *,
    center_id: str,
    depth: int,
    node_limit: int,
    edge_limit: int,
) -> BoundedProjection:
    """Select a deterministic bounded induced subgraph around one canonical."""

    node_by_id = {node.id: node for node in snapshot.nodes}
    if center_id not in node_by_id:
        raise KeyError(center_id)

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in snapshot.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)

    selected: list[str] = [center_id]
    selected_set = {center_id}
    frontier = [center_id]
    truncated = False
    for _ in range(depth):
        candidates = sorted(
            {
                neighbor
                for node_id in frontier
                for neighbor in adjacency.get(node_id, set())
                if neighbor not in selected_set
            }
        )
        remaining = node_limit - len(selected)
        if len(candidates) > remaining:
            truncated = True
        added = candidates[: max(remaining, 0)]
        selected.extend(added)
        selected_set.update(added)
        frontier = added
        if not frontier or len(selected) >= node_limit:
            if frontier and any(
                neighbor not in selected_set
                for node_id in frontier
                for neighbor in adjacency.get(node_id, set())
            ):
                truncated = True
            break

    induced = [
        edge
        for edge in snapshot.edges
        if edge.source in selected_set and edge.target in selected_set
    ]
    induced.sort(key=lambda edge: (-edge.support_count, edge.id))
    if len(induced) > edge_limit:
        truncated = True
    edges = induced[:edge_limit]
    return BoundedProjection(
        nodes=[node_by_id[node_id] for node_id in selected],
        edges=edges,
        truncated=truncated,
    )


def deterministic_communities(
    nodes: Iterable[CanonicalGraphNode | Mapping[str, Any]],
    edges: Iterable[CanonicalGraphEdge | Mapping[str, Any]],
    *,
    limit: int,
    max_iterations: int = 20,
) -> list[CanonicalCommunity]:
    """Run deterministic single-level weighted modularity local moving."""

    node_models = sorted(
        (
            node
            if isinstance(node, CanonicalGraphNode)
            else CanonicalGraphNode.model_validate(node)
            for node in nodes
        ),
        key=lambda item: item.id,
    )
    edge_models = sorted(
        (
            edge
            if isinstance(edge, CanonicalGraphEdge)
            else CanonicalGraphEdge.model_validate(edge)
            for edge in edges
        ),
        key=lambda item: item.id,
    )
    node_by_id = {node.id: node for node in node_models}
    weights: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for edge in edge_models:
        if edge.source == edge.target:
            continue
        weight = float(edge.support_count)
        weights[edge.source][edge.target] += weight
        weights[edge.target][edge.source] += weight

    active_ids = sorted(node_id for node_id in node_by_id if weights.get(node_id))
    if not active_ids:
        return []
    degree = {
        node_id: sum(weights[node_id].values())
        for node_id in active_ids
    }
    total_twice = sum(degree.values())
    if total_twice <= 0:
        return []

    assignment = {node_id: node_id for node_id in active_ids}
    totals = dict(degree)
    epsilon = 1e-12
    for _ in range(max_iterations):
        moved = False
        for node_id in active_ids:
            old = assignment[node_id]
            node_degree = degree[node_id]
            neighbor_weights: dict[str, float] = defaultdict(float)
            for neighbor, weight in weights[node_id].items():
                neighbor_weights[assignment[neighbor]] += weight

            totals[old] = totals.get(old, 0.0) - node_degree
            candidates = sorted({old, *neighbor_weights})
            best = old
            best_gain = (
                neighbor_weights.get(old, 0.0)
                - totals.get(old, 0.0) * node_degree / total_twice
            )
            for candidate in candidates:
                gain = (
                    neighbor_weights.get(candidate, 0.0)
                    - totals.get(candidate, 0.0) * node_degree / total_twice
                )
                if gain > best_gain + epsilon or (
                    abs(gain - best_gain) <= epsilon and candidate < best
                ):
                    best = candidate
                    best_gain = gain
            assignment[node_id] = best
            totals[best] = totals.get(best, 0.0) + node_degree
            if best != old:
                moved = True
        if not moved:
            break

    members_by_label: dict[str, set[str]] = defaultdict(set)
    for node_id, label in assignment.items():
        members_by_label[label].add(node_id)

    communities: list[CanonicalCommunity] = []
    for members in members_by_label.values():
        member_edges = [
            edge
            for edge in edge_models
            if edge.source in members and edge.target in members
        ]
        total_support = sum(edge.support_count for edge in member_edges)
        representative = min(
            (node_by_id[node_id] for node_id in members),
            key=lambda node: (
                -degree.get(node.id, 0.0),
                -node.source_entity_count,
                node.id,
            ),
        )
        document_ids = sorted(
            {
                document_id
                for node_id in members
                for document_id in node_by_id[node_id].document_ids
            }
        )
        communities.append(
            CanonicalCommunity(
                id=community_id(members),
                representative_node=representative,
                node_count=len(members),
                edge_count=len(member_edges),
                total_support=total_support,
                document_ids=document_ids,
            )
        )
    communities.sort(
        key=lambda item: (-item.node_count, -item.total_support, item.id)
    )
    return communities[:limit]
