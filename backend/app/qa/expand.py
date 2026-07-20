"""Read-only accepted canonical relation expansion for QA.

Chunk vector recall remains the evidence boundary.  This module only projects
eligible source ``RELATES`` facts through validated ``RESOLVES_TO`` links; it
never materializes canonical relationships or creates answer citations.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from neo4j import Driver

from app.qa.models import RelationPath, RelationProvenance, RetrievalContext

_PROVENANCE_LIMIT = 5

_EXPAND = """
UNWIND $chunk_ids AS selected_chunk_id
MATCH (selected_document:Document)-[:HAS_CHUNK]->(selected_chunk:Chunk {
  chunk_id: selected_chunk_id
})
WHERE selected_chunk.document_id = selected_document.document_id
MATCH (selected_chunk)-[:MENTIONS]->(selected_source:Entity)
WHERE selected_source.document_id = selected_document.document_id
  AND selected_source.resolution_status IS NULL
MATCH (selected_source)-[selected_resolution:RESOLVES_TO]
      ->(seed_canonical:CanonicalEntity)
WHERE selected_resolution.source_document_id = selected_source.document_id
  AND EXISTS {
    MATCH (selected_evidence_document:Document {
      document_id: selected_source.document_id
    })-[:HAS_CHUNK]->(selected_resolution_evidence:Chunk {
      chunk_id: selected_resolution.evidence_chunk_id
    })-[:MENTIONS]->(selected_source)
    WHERE selected_resolution_evidence.document_id = selected_source.document_id
  }
WITH DISTINCT seed_canonical
MATCH (source)-[source_resolution:RESOLVES_TO]
      ->(source_canonical:CanonicalEntity)
MATCH (source)-[relation:RELATES]->(target:Entity)
MATCH (target)-[target_resolution:RESOLVES_TO]
      ->(target_canonical:CanonicalEntity)
WHERE source_canonical.canonical_id = seed_canonical.canonical_id
  AND source.document_id = target.document_id
  AND source.resolution_status IS NULL
  AND target.resolution_status IS NULL
  AND source_canonical.canonical_id <> target_canonical.canonical_id
  AND relation.type IS NOT NULL
  AND trim(toString(relation.type)) <> ''
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
RETURN DISTINCT source_canonical.canonical_id AS source_canonical_id,
       source_canonical.canonical_name AS source_name,
       target_canonical.canonical_id AS target_canonical_id,
       target_canonical.canonical_name AS target_name,
       relation.type AS type,
       source.document_id AS document_id,
       relation.evidence_chunk_id AS evidence_chunk_id,
       source.entity_id AS source_entity_id,
       target.entity_id AS target_entity_id,
       relation.confidence AS confidence
ORDER BY source_canonical_id, target_canonical_id, type,
         document_id, evidence_chunk_id, source_entity_id, target_entity_id
"""


def canonical_path_id(source: str, target: str, relation_type: str) -> str:
    """Return a stable identity for one directed canonical relation key."""

    payload = json.dumps(
        [source, target, relation_type],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"canonical-path:v1:{hashlib.sha256(payload).hexdigest()}"


def _row_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "data"):
        return dict(row.data())
    return dict(row)


def _provenance_key(item: RelationProvenance) -> tuple[str, str, str, str]:
    return (
        item.document_id,
        item.evidence_chunk_id,
        item.source_entity_id,
        item.target_entity_id,
    )


def _confidence_rank(value: float | None) -> float:
    return float("-inf") if value is None else value


def aggregate_canonical_paths(
    records: Iterable[Mapping[str, Any]],
    *,
    provenance_limit: int = _PROVENANCE_LIMIT,
) -> list[RelationPath]:
    """Aggregate already eligible rows independently of input row order."""

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        row = _row_dict(record)
        source_id = str(row.get("source_canonical_id") or "").strip()
        target_id = str(row.get("target_canonical_id") or "").strip()
        relation_type = str(row.get("type") or "").strip()
        if not source_id or not target_id or not relation_type or source_id == target_id:
            continue
        key = (source_id, target_id, relation_type)
        group = grouped.setdefault(
            key,
            {
                "source_names": set(),
                "target_names": set(),
                "provenance": {},
            },
        )
        source_name = str(row.get("source_name") or "").strip()
        target_name = str(row.get("target_name") or "").strip()
        if source_name:
            group["source_names"].add(source_name)
        if target_name:
            group["target_names"].add(target_name)
        document_id = str(row.get("document_id") or "").strip()
        evidence_chunk_id = str(row.get("evidence_chunk_id") or "").strip()
        source_entity_id = str(row.get("source_entity_id") or "").strip()
        target_entity_id = str(row.get("target_entity_id") or "").strip()
        if not all(
            (document_id, evidence_chunk_id, source_entity_id, target_entity_id)
        ):
            continue
        confidence = row.get("confidence")
        if confidence is not None and not isinstance(confidence, (int, float)):
            continue
        provenance = RelationProvenance(
            document_id=document_id,
            evidence_chunk_id=evidence_chunk_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            confidence=confidence,
        )
        provenance_key = _provenance_key(provenance)
        previous = group["provenance"].get(provenance_key)
        if previous is None or _confidence_rank(provenance.confidence) > _confidence_rank(
            previous.confidence
        ):
            group["provenance"][provenance_key] = provenance

    paths: list[RelationPath] = []
    for (source_id, target_id, relation_type), group in grouped.items():
        provenance = sorted(
            group["provenance"].values(),
            key=_provenance_key,
        )
        if not provenance:
            continue
        source_names = sorted(group["source_names"])
        target_names = sorted(group["target_names"])
        paths.append(
            RelationPath(
                path_id=canonical_path_id(source_id, target_id, relation_type),
                source_canonical_id=source_id,
                source_name=source_names[0] if source_names else source_id,
                target_canonical_id=target_id,
                target_name=target_names[0] if target_names else target_id,
                type=relation_type,
                evidence_chunk_id=provenance[0].evidence_chunk_id,
                support_count=len(provenance),
                provenance=provenance[:provenance_limit],
                provenance_truncated=len(provenance) > provenance_limit,
            )
        )
    paths.sort(key=lambda path: (-path.support_count, path.path_id))
    return paths


def _path_key(path: RelationPath) -> tuple[str, str, str]:
    return (
        path.source_canonical_id or path.source_name,
        path.target_canonical_id or path.target_name,
        path.type,
    )


def merge_canonical_paths(paths: Iterable[RelationPath]) -> list[RelationPath]:
    """Merge repeated tool observations into one bounded path per canonical key."""

    grouped: dict[tuple[str, str, str], list[RelationPath]] = {}
    for path in paths:
        grouped.setdefault(_path_key(path), []).append(path)

    merged: list[RelationPath] = []
    for (source_key, target_key, relation_type), candidates in grouped.items():
        provenance_by_key: dict[
            tuple[str, str, str, str], RelationProvenance
        ] = {}
        for candidate in candidates:
            for item in candidate.provenance:
                key = _provenance_key(item)
                previous = provenance_by_key.get(key)
                if previous is None or _confidence_rank(item.confidence) > _confidence_rank(
                    previous.confidence
                ):
                    provenance_by_key[key] = item
        all_provenance = sorted(provenance_by_key.values(), key=_provenance_key)
        support_count = max(
            len(all_provenance),
            *(candidate.support_count for candidate in candidates),
        )
        source_ids = sorted(
            {
                candidate.source_canonical_id
                for candidate in candidates
                if candidate.source_canonical_id
            }
        )
        target_ids = sorted(
            {
                candidate.target_canonical_id
                for candidate in candidates
                if candidate.target_canonical_id
            }
        )
        source_names = sorted({candidate.source_name for candidate in candidates})
        target_names = sorted({candidate.target_name for candidate in candidates})
        evidence_ids = sorted(
            {
                candidate.evidence_chunk_id
                for candidate in candidates
                if candidate.evidence_chunk_id
            }
        )
        source_id = source_ids[0] if source_ids else None
        target_id = target_ids[0] if target_ids else None
        bounded = all_provenance[:_PROVENANCE_LIMIT]
        merged.append(
            RelationPath(
                path_id=canonical_path_id(
                    source_id or source_key,
                    target_id or target_key,
                    relation_type,
                ),
                source_canonical_id=source_id,
                source_name=source_names[0],
                target_canonical_id=target_id,
                target_name=target_names[0],
                type=relation_type,
                evidence_chunk_id=(
                    bounded[0].evidence_chunk_id
                    if bounded
                    else (evidence_ids[0] if evidence_ids else "")
                ),
                support_count=support_count,
                provenance=bounded,
                provenance_truncated=(
                    any(candidate.provenance_truncated for candidate in candidates)
                    or support_count > len(bounded)
                ),
            )
        )
    merged.sort(key=lambda path: (-path.support_count, path.path_id))
    return merged


def expand_entities(
    driver: Driver, chunk_ids: list[str], *, database: str = "neo4j"
) -> RetrievalContext:
    """Project accepted canonical relations starting at the supplied Chunks."""

    normalized_ids = sorted(
        {
            chunk_id.strip()
            for chunk_id in chunk_ids
            if isinstance(chunk_id, str) and chunk_id.strip()
        }
    )
    if not normalized_ids:
        return RetrievalContext(paths=[])
    records, _, _ = driver.execute_query(
        _EXPAND,
        chunk_ids=normalized_ids,
        database_=database,
    )
    return RetrievalContext(paths=aggregate_canonical_paths(records))
