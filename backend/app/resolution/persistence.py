"""Neo4j persistence for the non-destructive canonical entity overlay."""

from __future__ import annotations

from collections.abc import Iterable

from neo4j import Driver

from app.resolution.identity import RESOLUTION_VERSION
from app.resolution.models import (
    AcceptedResolutionRecord,
    AliasRecord,
    CanonicalEntityReference,
    ResolutionCandidate,
    ResolutionStatus,
    SourceEntityRecord,
)
from app.resolution.normalization import normalize_name


_LOAD_CANONICALS = """
MATCH (canonical:CanonicalEntity)
RETURN canonical.canonical_id AS canonical_id,
       canonical.canonical_name AS canonical_name,
       coalesce(canonical.entity_type, '') AS entity_type
ORDER BY canonical.canonical_id
"""

_LOAD_ALIASES = """
MATCH (document:Document)-[:HAS_CHUNK]->(evidence:Chunk)-[:MENTIONS]->(source:Entity)
MATCH (source)-[resolution:RESOLVES_TO]->(canonical:CanonicalEntity)
WHERE resolution.method = 'alias'
  AND resolution.evidence_chunk_id = evidence.chunk_id
  AND resolution.source_document_id = source.document_id
  AND document.document_id = source.document_id
RETURN source.name AS alias,
       canonical.canonical_id AS canonical_id,
       source.entity_id AS source_entity_id,
       source.document_id AS source_document_id,
       evidence.chunk_id AS source_chunk_id
ORDER BY source.entity_id, evidence.chunk_id, canonical.canonical_id
"""

_LOAD_EXISTING_ACCEPTED = """
MATCH (document:Document)-[:HAS_CHUNK]->(evidence:Chunk)-[:MENTIONS]->(source:Entity)
MATCH (source)-[resolution:RESOLVES_TO]->(canonical:CanonicalEntity)
WHERE resolution.evidence_chunk_id = evidence.chunk_id
  AND resolution.source_document_id = source.document_id
  AND document.document_id = source.document_id
RETURN source.entity_id AS source_entity_id,
       source.document_id AS source_document_id,
       evidence.chunk_id AS source_chunk_id,
       canonical.canonical_id AS canonical_id,
       resolution.method AS method,
       resolution.score AS score,
       resolution.reason AS reason
ORDER BY source.entity_id
"""

_VALIDATE_ALIASES = """
UNWIND $aliases AS alias
MATCH (source:Entity {
  entity_id: alias.source_entity_id,
  document_id: alias.source_document_id
})
MATCH (document:Document {document_id: alias.source_document_id})
      -[:HAS_CHUNK]->(evidence:Chunk {chunk_id: alias.source_chunk_id})
      -[:MENTIONS]->(source)
MATCH (canonical:CanonicalEntity {canonical_id: alias.canonical_id})
RETURN alias.alias AS alias,
       alias.canonical_id AS canonical_id,
       alias.source_entity_id AS source_entity_id,
       alias.source_document_id AS source_document_id,
       alias.source_chunk_id AS source_chunk_id,
       source.name AS source_name
ORDER BY source_entity_id, source_chunk_id, canonical_id
"""

_LOAD_SOURCES = """
MATCH (source:Entity)
OPTIONAL MATCH (document:Document)-[:HAS_CHUNK]->(evidence:Chunk)-[:MENTIONS]->(source)
WHERE document.document_id = source.document_id
RETURN source.entity_id AS entity_id,
       source.name AS name,
       coalesce(source.entity_type, '') AS entity_type,
       coalesce(source.normalized_name, '') AS normalized_name,
       source.document_id AS document_id,
       [chunk_id IN collect(DISTINCT evidence.chunk_id) WHERE chunk_id IS NOT NULL]
         AS mention_chunk_ids
ORDER BY source.entity_id
"""

_WRITE_ACCEPTED = """
MATCH (source:Entity {
  entity_id: $source_entity_id,
  document_id: $source_document_id
})
MATCH (document:Document {document_id: $source_document_id})
      -[:HAS_CHUNK]->(evidence:Chunk {chunk_id: $evidence_chunk_id})
      -[:MENTIONS]->(source)
OPTIONAL MATCH (source)-[previous:RESOLVES_TO]->(:CanonicalEntity)
WITH source, evidence, collect(previous) AS previous_links
FOREACH (previous IN previous_links | DELETE previous)
MERGE (canonical:CanonicalEntity {canonical_id: $canonical_id})
  ON CREATE SET canonical.canonical_name = $canonical_name,
                canonical.normalized_name = $normalized_name,
                canonical.entity_type = $entity_type,
                canonical.resolution_version = $resolution_version
MERGE (source)-[resolution:RESOLVES_TO]->(canonical)
SET resolution.method = $method,
    resolution.score = $score,
    resolution.reason = $reason,
    resolution.source_document_id = $source_document_id,
    resolution.evidence_chunk_id = $evidence_chunk_id
REMOVE source.resolution_status,
       source.resolution_method,
       source.resolution_score,
       source.resolution_reason,
       source.candidate_canonical_ids
RETURN count(source) AS written
"""

_WRITE_REVIEW_OR_UNRESOLVED = """
MATCH (source:Entity {
  entity_id: $source_entity_id,
  document_id: $source_document_id
})
OPTIONAL MATCH (source)-[previous:RESOLVES_TO]->(:CanonicalEntity)
WITH source, collect(previous) AS previous_links
FOREACH (previous IN previous_links | DELETE previous)
SET source.resolution_status = $status,
    source.resolution_method = $method,
    source.resolution_score = $score,
    source.resolution_reason = $reason,
    source.candidate_canonical_ids = $candidate_canonical_ids
RETURN count(source) AS written
"""

_REMOVE_ORPHANS = """
MATCH (canonical:CanonicalEntity)
WHERE NOT EXISTS {
  MATCH (:Entity)-[:RESOLVES_TO]->(canonical)
}
DETACH DELETE canonical
RETURN count(canonical) AS deleted
"""


def _records(result) -> list:
    return list(result[0])


class CanonicalOverlayStore:
    """Small persistence boundary shared by runtime ingestion and backfill."""

    def __init__(self, driver: Driver, *, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    def _execute(self, query: str, **params):
        return self.driver.execute_query(query, **params, database_=self.database)

    def load_canonicals(self) -> list[CanonicalEntityReference]:
        return [
            CanonicalEntityReference.model_validate(dict(record))
            for record in _records(self._execute(_LOAD_CANONICALS))
        ]

    def load_reconstructed_aliases(self) -> list[AliasRecord]:
        return [
            AliasRecord.model_validate(dict(record))
            for record in _records(self._execute(_LOAD_ALIASES))
        ]

    def load_existing_resolutions(self) -> dict[str, AcceptedResolutionRecord]:
        records = [
            AcceptedResolutionRecord.model_validate(dict(record))
            for record in _records(self._execute(_LOAD_EXISTING_ACCEPTED))
        ]
        return {record.source_entity_id: record for record in records}

    def validate_aliases(self, records: Iterable[AliasRecord]) -> list[AliasRecord]:
        requested = sorted(
            (AliasRecord.model_validate(record) for record in records),
            key=lambda item: (
                item.source_entity_id,
                item.source_chunk_id,
                item.canonical_id,
                normalize_name(item.alias),
            ),
        )
        if not requested:
            return []
        payload = [record.model_dump() for record in requested]
        rows = _records(self._execute(_VALIDATE_ALIASES, aliases=payload))
        validated: list[AliasRecord] = []
        for row in rows:
            data = dict(row)
            source_name = data.pop("source_name")
            record = AliasRecord.model_validate(data)
            if normalize_name(record.alias) == normalize_name(source_name):
                validated.append(record)
        if [item.model_dump() for item in validated] != payload:
            raise ValueError("alias provenance is not valid in the source graph")
        return validated

    def load_source_entities(self) -> list[SourceEntityRecord]:
        return [
            SourceEntityRecord.model_validate(dict(record))
            for record in _records(self._execute(_LOAD_SOURCES))
        ]

    def write_decision(
        self, source: SourceEntityRecord, decision: ResolutionCandidate
    ) -> None:
        if source.entity_id != decision.source_entity_id:
            raise ValueError("decision source_entity_id does not match source record")
        if source.document_id != decision.source_document_id:
            raise ValueError("decision source_document_id does not match source record")

        common = {
            "source_entity_id": source.entity_id,
            "source_document_id": source.document_id,
            "status": decision.status.value,
            "method": decision.method.value,
            "score": decision.score,
            "reason": decision.reason,
            "candidate_canonical_ids": decision.candidate_canonical_ids,
        }
        if decision.status is ResolutionStatus.ACCEPTED:
            if decision.evidence is None or decision.canonical_id is None:
                raise ValueError("accepted decision requires evidence and canonical_id")
            result = self._execute(
                _WRITE_ACCEPTED,
                **common,
                evidence_chunk_id=decision.evidence.source_chunk_id,
                canonical_id=decision.canonical_id,
                canonical_name=source.name,
                normalized_name=normalize_name(source.name),
                entity_type=source.entity_type,
                resolution_version=RESOLUTION_VERSION,
            )
        else:
            result = self._execute(_WRITE_REVIEW_OR_UNRESOLVED, **common)
        records = _records(result)
        if not records or records[0]["written"] != 1:
            raise RuntimeError(
                "canonical decision could not match source/document/mention evidence"
            )

    def remove_orphan_canonicals(self) -> int:
        records = _records(self._execute(_REMOVE_ORPHANS))
        return int(records[0]["deleted"]) if records else 0
