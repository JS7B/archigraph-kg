"""Deterministic, provenance-preserving entity resolution rules."""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping
from typing import Any

from app.resolution.models import (
    AliasRecord,
    CanonicalEntityReference,
    ResolutionCandidate,
    ResolutionEvidence,
    ResolutionMethod,
    ResolutionStatus,
)
from app.resolution.normalization import normalize_name


class DeterministicResolver:
    """Resolve source mentions using exact keys, aliases, then review-only fuzzy matches."""

    def __init__(
        self,
        canonicals: Iterable[CanonicalEntityReference | Mapping[str, Any]] = (),
        *,
        aliases: Iterable[AliasRecord | Mapping[str, Any]] | Mapping[str, str] = (),
        fuzzy_threshold: float = 0.72,
        ambiguity_margin: float = 0.03,
        **options: Any,
    ) -> None:
        if "canonical_entities" in options:
            canonicals = options.pop("canonical_entities")
        if "canonical_refs" in options:
            canonicals = options.pop("canonical_refs")
        if "review_threshold" in options:
            fuzzy_threshold = options.pop("review_threshold")
        if "fuzzy_review_threshold" in options:
            fuzzy_threshold = options.pop("fuzzy_review_threshold")
        if "min_similarity" in options:
            fuzzy_threshold = options.pop("min_similarity")
        if options:
            unknown = next(iter(options))
            raise TypeError(f"unexpected resolver option: {unknown}")
        if not 0 <= fuzzy_threshold <= 1:
            raise ValueError("fuzzy_threshold must be between 0 and 1")
        if ambiguity_margin < 0:
            raise ValueError("ambiguity_margin must not be negative")

        self.fuzzy_threshold = float(fuzzy_threshold)
        self.ambiguity_margin = float(ambiguity_margin)
        self._canonicals: dict[str, CanonicalEntityReference] = {}
        self._exact: dict[str, set[str]] = {}
        self._aliases: dict[str, set[str]] = {}

        for canonical in canonicals:
            self.register_canonical(canonical)
        if isinstance(aliases, Mapping):
            for alias, canonical_id in aliases.items():
                self.register_alias(alias, canonical_id)
        else:
            for alias in aliases:
                self.register_alias(alias)

    def register_canonical(
        self, canonical: CanonicalEntityReference | Mapping[str, Any]
    ) -> CanonicalEntityReference:
        reference = (
            canonical
            if isinstance(canonical, CanonicalEntityReference)
            else CanonicalEntityReference.model_validate(canonical)
        )
        self._canonicals[reference.canonical_id] = reference
        self._add_key(self._exact, reference.canonical_name, reference.canonical_id)
        return reference

    def register_alias(
        self,
        alias: AliasRecord | Mapping[str, Any] | str,
        canonical_id: str | None = None,
    ) -> None:
        """Register an explicit alias; conflicting targets remain ambiguous."""

        if isinstance(alias, str):
            if not canonical_id or not canonical_id.strip():
                raise ValueError("canonical_id is required when alias is a string")
            alias_name = alias
        elif isinstance(alias, AliasRecord):
            alias_name, canonical_id = alias.alias, alias.canonical_id
        else:
            record = AliasRecord.model_validate(alias)
            alias_name, canonical_id = record.alias, record.canonical_id
        if canonical_id not in self._canonicals:
            raise ValueError(f"unknown canonical_id: {canonical_id}")
        self._add_key(self._aliases, alias_name, canonical_id)

    @staticmethod
    def _add_key(index: dict[str, set[str]], name: str, canonical_id: str) -> None:
        key = normalize_name(name)
        if not key:
            raise ValueError("name must not normalize to an empty key")
        index.setdefault(key, set()).add(canonical_id)

    def resolve(
        self,
        source_entity_id: str | Any,
        source_name: str | None = None,
        source_document_id: str | None = None,
        source_chunk_id: str | None = None,
        **aliases: Any,
    ) -> ResolutionCandidate:
        """Resolve one source mention while retaining its original identity.

        ``entity``-like objects and camel-free aliases (``name``, ``document_id``,
        ``chunk_id``) are accepted for convenient adapters without coupling this
        resolver to extraction models.
        """

        source_entity_id, source_name, source_document_id, source_chunk_id = self._coerce_input(
            source_entity_id,
            source_name or aliases.pop("name", None),
            source_document_id or aliases.pop("document_id", None),
            source_chunk_id or aliases.pop("chunk_id", None),
        )
        if aliases:
            unknown = next(iter(aliases))
            raise TypeError(f"unexpected resolve option: {unknown}")
        key = normalize_name(source_name)
        if not key:
            return self._unresolved(
                source_entity_id, source_name, source_document_id, source_chunk_id, "empty normalized name"
            )

        exact = self._exact.get(key, set())
        if exact:
            return self._from_index(
                exact,
                source_entity_id,
                source_name,
                source_document_id,
                source_chunk_id,
                ResolutionMethod.EXACT,
                "normalized canonical key matches",
            )

        alias = self._aliases.get(key, set())
        if alias:
            return self._from_index(
                alias,
                source_entity_id,
                source_name,
                source_document_id,
                source_chunk_id,
                ResolutionMethod.ALIAS,
                "explicit alias matches",
            )

        return self._fuzzy(
            key, source_entity_id, source_name, source_document_id, source_chunk_id
        )

    @staticmethod
    def _coerce_input(
        source_entity_id: str | Any,
        source_name: str | None,
        source_document_id: str | None,
        source_chunk_id: str | None,
    ) -> tuple[str, str, str, str]:
        if not isinstance(source_entity_id, str):
            entity = source_entity_id
            source_entity_id = getattr(entity, "entity_id", None) or entity.get("entity_id")
            source_name = source_name or getattr(entity, "name", None) or entity.get("name")
            chunks = getattr(entity, "mention_chunk_ids", None) or entity.get("mention_chunk_ids", [])
            source_chunk_id = source_chunk_id or (chunks[0] if chunks else None)
        source_document_id = source_document_id or source_entity_id.split("::", 1)[0]
        if not all(isinstance(value, str) and value.strip() for value in (source_entity_id, source_name, source_document_id, source_chunk_id)):
            raise ValueError("source entity id, name, document id, and chunk id are required")
        return source_entity_id, source_name, source_document_id, source_chunk_id

    def _from_index(
        self,
        ids: set[str],
        source_entity_id: str,
        source_name: str,
        source_document_id: str,
        source_chunk_id: str,
        method: ResolutionMethod,
        reason: str,
    ) -> ResolutionCandidate:
        if len(ids) != 1:
            score = 1.0
            evidence = ResolutionEvidence(
                source_entity_id=source_entity_id,
                source_document_id=source_document_id,
                source_chunk_id=source_chunk_id,
                canonical_id=None,
                method=method,
                score=score,
                reason=f"ambiguous {method.value} key maps to {len(ids)} canonical entities",
            )
            return ResolutionCandidate(
                source_entity_id=source_entity_id,
                source_name=source_name,
                source_document_id=source_document_id,
                source_chunk_id=source_chunk_id,
                status=ResolutionStatus.REVIEW,
                method=method,
                score=score,
                evidence=evidence,
                reason=evidence.reason,
            )
        canonical_id = next(iter(ids))
        evidence = ResolutionEvidence(
            source_entity_id=source_entity_id,
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            canonical_id=canonical_id,
            method=method,
            score=1.0,
            reason=reason,
        )
        return ResolutionCandidate(
            source_entity_id=source_entity_id,
            source_name=source_name,
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            canonical_id=canonical_id,
            status=ResolutionStatus.ACCEPTED,
            method=method,
            score=1.0,
            evidence=evidence,
            reason=reason,
        )

    def _fuzzy(
        self,
        key: str,
        source_entity_id: str,
        source_name: str,
        source_document_id: str,
        source_chunk_id: str,
    ) -> ResolutionCandidate:
        scored = sorted(
            (
                difflib.SequenceMatcher(None, key, normalize_name(reference.canonical_name)).ratio(),
                canonical_id,
            )
            for canonical_id, reference in self._canonicals.items()
        )
        scored.reverse()
        if not scored or scored[0][0] < self.fuzzy_threshold:
            return self._unresolved(
                source_entity_id,
                source_name,
                source_document_id,
                source_chunk_id,
                "no exact, alias, or sufficiently similar canonical name",
            )
        best_score, best_id = scored[0]
        tied = len(scored) > 1 and best_score - scored[1][0] <= self.ambiguity_margin
        if tied:
            reason = "ambiguous fuzzy candidates require review"
            evidence = ResolutionEvidence(
                source_entity_id=source_entity_id,
                source_document_id=source_document_id,
                source_chunk_id=source_chunk_id,
                canonical_id=None,
                method=ResolutionMethod.FUZZY,
                score=best_score,
                reason=reason,
            )
            return ResolutionCandidate(
                source_entity_id=source_entity_id,
                source_name=source_name,
                source_document_id=source_document_id,
                source_chunk_id=source_chunk_id,
                status=ResolutionStatus.REVIEW,
                method=ResolutionMethod.FUZZY,
                score=best_score,
                evidence=evidence,
                reason=reason,
            )
        evidence = ResolutionEvidence(
            source_entity_id=source_entity_id,
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            canonical_id=best_id,
            method=ResolutionMethod.FUZZY,
            score=best_score,
            reason="fuzzy candidate requires review before merge",
        )
        return ResolutionCandidate(
            source_entity_id=source_entity_id,
            source_name=source_name,
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            canonical_id=best_id,
            status=ResolutionStatus.REVIEW,
            method=ResolutionMethod.FUZZY,
            score=best_score,
            evidence=evidence,
            reason="fuzzy candidate requires review before merge",
        )

    @staticmethod
    def _unresolved(
        source_entity_id: str,
        source_name: str,
        source_document_id: str,
        source_chunk_id: str,
        reason: str,
    ) -> ResolutionCandidate:
        return ResolutionCandidate(
            source_entity_id=source_entity_id,
            source_name=source_name,
            source_document_id=source_document_id,
            source_chunk_id=source_chunk_id,
            status=ResolutionStatus.UNRESOLVED,
            method=ResolutionMethod.FALLBACK,
            reason=reason,
        )


EntityResolver = DeterministicResolver
