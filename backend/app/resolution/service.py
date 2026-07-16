"""Runtime orchestration for deterministic canonical entity resolution."""

from __future__ import annotations

from collections.abc import Iterable

from neo4j import Driver

from app.resolution.identity import canonical_id_for_name
from app.resolution.models import (
    AcceptedResolutionRecord,
    AliasRecord,
    CanonicalEntityReference,
    CanonicalizationResult,
    ResolutionCandidate,
    ResolutionEvidence,
    ResolutionMethod,
    ResolutionStatus,
    SourceEntityRecord,
)
from app.resolution.normalization import normalize_name
from app.resolution.persistence import CanonicalOverlayStore
from app.resolution.resolver import DeterministicResolver


def _unresolved_missing_mention(source: SourceEntityRecord) -> ResolutionCandidate:
    return ResolutionCandidate(
        source_entity_id=source.entity_id,
        source_name=source.name,
        source_document_id=source.document_id,
        source_chunk_id=None,
        status=ResolutionStatus.UNRESOLVED,
        method=ResolutionMethod.FALLBACK,
        reason="missing mention provenance",
    )


def _bootstrap(source: SourceEntityRecord, chunk_id: str) -> ResolutionCandidate:
    canonical_id = canonical_id_for_name(source.name)
    reason = "new normalized name bootstrapped deterministically"
    evidence = ResolutionEvidence(
        source_entity_id=source.entity_id,
        source_document_id=source.document_id,
        source_chunk_id=chunk_id,
        canonical_id=canonical_id,
        method=ResolutionMethod.BOOTSTRAP,
        score=1.0,
        reason=reason,
    )
    return ResolutionCandidate(
        source_entity_id=source.entity_id,
        source_name=source.name,
        source_document_id=source.document_id,
        source_chunk_id=chunk_id,
        canonical_id=canonical_id,
        status=ResolutionStatus.ACCEPTED,
        method=ResolutionMethod.BOOTSTRAP,
        score=1.0,
        evidence=evidence,
        reason=reason,
    )


def _preserve_existing(
    source: SourceEntityRecord,
    decision: ResolutionCandidate,
    existing: AcceptedResolutionRecord | None,
) -> ResolutionCandidate:
    """Keep accepted edge provenance stable when the target did not change."""

    if (
        existing is None
        or decision.status is not ResolutionStatus.ACCEPTED
        or decision.canonical_id != existing.canonical_id
        or existing.source_document_id != source.document_id
        or existing.source_chunk_id not in source.mention_chunk_ids
    ):
        return decision
    evidence = ResolutionEvidence(
        source_entity_id=source.entity_id,
        source_document_id=source.document_id,
        source_chunk_id=existing.source_chunk_id,
        canonical_id=existing.canonical_id,
        method=existing.method,
        score=existing.score,
        reason=existing.reason,
    )
    return ResolutionCandidate(
        source_entity_id=source.entity_id,
        source_name=source.name,
        source_document_id=source.document_id,
        source_chunk_id=existing.source_chunk_id,
        canonical_id=existing.canonical_id,
        status=ResolutionStatus.ACCEPTED,
        method=existing.method,
        score=existing.score,
        evidence=evidence,
        reason=existing.reason,
    )


def resolve_source_entities(
    driver: Driver,
    sources: Iterable[SourceEntityRecord],
    *,
    aliases: Iterable[AliasRecord] = (),
    database: str = "neo4j",
    fuzzy_threshold: float = 0.72,
    ambiguity_margin: float = 0.03,
    store: CanonicalOverlayStore | None = None,
) -> CanonicalizationResult:
    """Resolve and persist source entities in stable ``entity_id`` order."""

    overlay = store or CanonicalOverlayStore(driver, database=database)
    canonicals = overlay.load_canonicals()
    reconstructed_aliases = overlay.load_reconstructed_aliases()
    existing_resolutions = overlay.load_existing_resolutions()
    validated_aliases = overlay.validate_aliases(aliases)
    resolver = DeterministicResolver(
        canonicals,
        aliases=[*reconstructed_aliases, *validated_aliases],
        fuzzy_threshold=fuzzy_threshold,
        ambiguity_margin=ambiguity_margin,
    )

    decisions: list[ResolutionCandidate] = []
    diagnostics: list[str] = []
    for source in sorted(
        (SourceEntityRecord.model_validate(record) for record in sources),
        key=lambda item: item.entity_id,
    ):
        if not source.mention_chunk_ids:
            decision = _unresolved_missing_mention(source)
        else:
            evidence_chunk_id = source.mention_chunk_ids[0]
            decision = resolver.resolve(
                source.entity_id,
                source.name,
                source.document_id,
                evidence_chunk_id,
            )
            if (
                decision.status is ResolutionStatus.UNRESOLVED
                and normalize_name(source.name)
            ):
                decision = _bootstrap(source, evidence_chunk_id)
                resolver.register_canonical(
                    CanonicalEntityReference(
                        canonical_id=decision.canonical_id,
                        canonical_name=source.name,
                        entity_type=source.entity_type,
                    )
                )
            decision = _preserve_existing(
                source, decision, existing_resolutions.get(source.entity_id)
            )
        overlay.write_decision(source, decision)
        decisions.append(decision)
        if decision.status is not ResolutionStatus.ACCEPTED:
            candidates = ",".join(decision.candidate_canonical_ids) or "none"
            diagnostics.append(
                f"resolution {source.entity_id}: {decision.status.value} "
                f"({decision.method.value}; candidates={candidates}): {decision.reason}"
            )

    overlay.remove_orphan_canonicals()
    accepted = sum(item.status is ResolutionStatus.ACCEPTED for item in decisions)
    review = sum(item.status is ResolutionStatus.REVIEW for item in decisions)
    unresolved = sum(item.status is ResolutionStatus.UNRESOLVED for item in decisions)
    bootstrapped = sum(item.method is ResolutionMethod.BOOTSTRAP for item in decisions)
    diagnostics.append(
        "resolution summary: "
        f"accepted={accepted}, review={review}, unresolved={unresolved}, "
        f"bootstrapped={bootstrapped}"
    )
    return CanonicalizationResult(
        decisions=decisions,
        diagnostics=diagnostics,
        accepted_count=accepted,
        review_count=review,
        unresolved_count=unresolved,
        bootstrap_count=bootstrapped,
    )
