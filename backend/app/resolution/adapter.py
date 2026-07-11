"""Pure integration between extraction's ``MergedEntity`` and resolution.

The adapter deliberately stops at an in-memory, provenance-carrying result.
Neo4j writers can consume ``ResolutionBatch.groups`` later, while unresolved
and review candidates remain available in ``candidates`` and ``diagnostics``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from app.resolution.models import (
    CanonicalEntityReference,
    ResolutionBatch,
    ResolutionCandidate,
    ResolutionGroup,
    ResolutionStatus,
)
from app.resolution.resolver import DeterministicResolver


class ResolutionAdapter:
    """Adapt MergedEntity-like records without mutating or persisting them."""

    def __init__(
        self,
        resolver: DeterministicResolver | None = None,
        *,
        canonicals: Iterable[CanonicalEntityReference | Mapping[str, Any]] = (),
        aliases: Iterable[Any] | Mapping[str, str] = (),
    ) -> None:
        if resolver is not None and (canonicals or aliases):
            raise ValueError("provide resolver or canonicals/aliases, not both")
        self._resolver = resolver
        self._canonicals = tuple(canonicals)
        self._aliases = aliases

    def adapt(self, entities: Iterable[Any]) -> ResolutionBatch:
        """Resolve entities and assemble deterministic canonical groups."""

        records = [self._coerce_entity(entity) for entity in entities]
        resolver = self._make_resolver(records)
        candidates: list[ResolutionCandidate] = []
        diagnostics: list[str] = []
        groups: dict[str, ResolutionGroup] = {}

        for entity in records:
            entity_id = entity.entity_id
            document_id = entity_id.split("::", 1)[0] or entity_id
            mentions = list(dict.fromkeys(entity.mention_chunk_ids))
            source_chunk_id = mentions[0] if mentions else f"{entity_id}::unattributed"
            if not mentions:
                diagnostics.append(
                    f"{entity_id}: missing mention provenance; using document-scoped fallback"
                )
                candidate = ResolutionCandidate(
                    source_entity_id=entity_id,
                    source_name=entity.name,
                    source_document_id=document_id,
                    source_chunk_id=source_chunk_id,
                    reason="missing mention provenance",
                )
            else:
                candidate = resolver.resolve(
                    entity_id,
                    entity.name,
                    document_id,
                    source_chunk_id,
                )
            candidates.append(candidate)

            accepted = candidate.status is ResolutionStatus.ACCEPTED
            target_id = candidate.canonical_id if accepted else entity_id
            fallback = not accepted
            canonical_name = self._canonical_name(resolver, target_id, entity.name)
            group = groups.get(target_id)
            if group is None:
                group = ResolutionGroup(
                    canonical_id=target_id,
                    canonical_name=canonical_name,
                    entity_type=entity.type,
                    source_entity_ids=[entity_id],
                    source_document_ids=[document_id],
                    fallback=fallback,
                )
                groups[target_id] = group
            self._append_unique(group.source_entity_ids, entity_id)
            self._append_unique(group.source_document_ids, document_id)
            self._append_unique(group.aliases, entity.name)
            for chunk_id in mentions:
                self._append_unique(group.mention_chunk_ids, chunk_id)
            if candidate.evidence is not None:
                for chunk_id in mentions or [source_chunk_id]:
                    evidence = candidate.evidence.model_copy(update={"source_chunk_id": chunk_id})
                    if evidence not in group.evidence:
                        group.evidence.append(evidence)
            if candidate.status is not ResolutionStatus.ACCEPTED:
                diagnostics.append(f"{entity_id}: {candidate.status.value}: {candidate.reason}")

        return ResolutionBatch(
            candidates=candidates,
            groups=list(groups.values()),
            diagnostics=diagnostics,
        )

    resolve = adapt

    def _make_resolver(self, records: list[Any]) -> DeterministicResolver:
        if self._resolver is not None:
            return self._resolver
        if self._canonicals or self._aliases:
            return DeterministicResolver(self._canonicals, aliases=self._aliases)

        # With no external canonical registry, the first spelling of each
        # normalized name establishes a local canonical identity.  This is
        # deterministic and keeps the adapter useful in extraction previews.
        resolver = DeterministicResolver()
        seen: set[str] = set()
        for entity in records:
            key = entity.normalized_name
            if key in seen:
                continue
            seen.add(key)
            resolver.register_canonical(
                CanonicalEntityReference(
                    canonical_id=entity.entity_id,
                    canonical_name=entity.name,
                    entity_type=entity.type,
                    source_document_ids=[entity.entity_id.split("::", 1)[0]],
                    source_chunk_ids=list(entity.mention_chunk_ids),
                )
            )
        return resolver

    @staticmethod
    def _canonical_name(
        resolver: DeterministicResolver, canonical_id: str, fallback: str
    ) -> str:
        reference = getattr(resolver, "_canonicals", {}).get(canonical_id)
        return reference.canonical_name if reference is not None else fallback

    @staticmethod
    def _append_unique(values: list[str], value: str) -> None:
        if value and value not in values:
            values.append(value)

    @staticmethod
    def _coerce_entity(entity: Any) -> Any:
        from app.extraction.models import MergedEntity

        if isinstance(entity, MergedEntity):
            return deepcopy(entity)
        if isinstance(entity, Mapping):
            return MergedEntity.model_validate(deepcopy(entity))
        return MergedEntity.model_validate(deepcopy(entity), from_attributes=True)


def adapt_merged_entities(
    entities: Iterable[Any],
    resolver: DeterministicResolver | None = None,
    **options: Any,
) -> ResolutionBatch:
    """Functional adapter alias for callers that prefer a one-shot API."""

    return ResolutionAdapter(resolver, **options).adapt(entities)


resolve_entities = adapt_merged_entities
resolve_merged_entities = adapt_merged_entities
