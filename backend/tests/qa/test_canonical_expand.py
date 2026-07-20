"""Deterministic contract tests for accepted-only canonical QA expansion."""

from __future__ import annotations

import re

from app.graph.search import ChunkHit
from app.qa import agent as agent_mod
from app.qa.expand import _EXPAND, expand_entities
from app.qa.models import RelationPath, RelationProvenance, RetrievalContext


class FakeDriver:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, dict]] = []

    def execute_query(self, query: str, **params):
        self.calls.append((query, params))
        return list(self.rows), None, None


def _fact(
    source: str = "canonical:a",
    target: str = "canonical:b",
    relation_type: str = "uses",
    *,
    document_id: str = "doc-a",
    chunk_id: str = "doc-a#0",
    source_entity_id: str = "doc-a::a",
    target_entity_id: str = "doc-a::b",
    confidence: float | None = 0.8,
) -> dict:
    return {
        "source_canonical_id": source,
        "source_name": "Alpha",
        "target_canonical_id": target,
        "target_name": "Beta",
        "type": relation_type,
        "document_id": document_id,
        "evidence_chunk_id": chunk_id,
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
        "confidence": confidence,
    }


def _hit(chunk_id: str) -> ChunkHit:
    document_id, _, suffix = chunk_id.partition("#")
    return ChunkHit(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=int(suffix or 0),
        text=f"evidence for {chunk_id}",
        char_start=0,
        char_end=8,
        score=0.9,
    )


def _provenance(document_id: str, chunk_id: str) -> RelationProvenance:
    return RelationProvenance(
        document_id=document_id,
        evidence_chunk_id=chunk_id,
        source_entity_id=f"{document_id}::a",
        target_entity_id=f"{document_id}::b",
        confidence=0.8,
    )


def _path(document_id: str, chunk_id: str) -> RelationPath:
    return RelationPath(
        path_id="canonical-path:v1:stable",
        source_canonical_id="canonical:a",
        source_name="Alpha",
        target_canonical_id="canonical:b",
        target_name="Beta",
        type="uses",
        evidence_chunk_id=chunk_id,
        support_count=1,
        provenance=[_provenance(document_id, chunk_id)],
    )


def test_query_is_read_only_and_freezes_every_accepted_evidence_boundary():
    compact = " ".join(_EXPAND.split())

    assert "UNWIND $chunk_ids AS selected_chunk_id" in compact
    assert "(selected_document:Document)-[:HAS_CHUNK]->(selected_chunk:Chunk" in compact
    assert "(selected_chunk)-[:MENTIONS]->(selected_source:Entity)" in compact
    assert re.search(
        r"\(selected_source\)-\[selected_resolution:RESOLVES_TO\]\s*->",
        compact,
    )
    assert "selected_source.resolution_status IS NULL" in compact
    assert "selected_resolution.source_document_id = selected_source.document_id" in compact
    assert "chunk_id: selected_resolution.evidence_chunk_id" in compact
    assert "(selected_resolution_evidence:Chunk" in compact
    assert "-[:MENTIONS]->(selected_source)" in compact
    assert re.search(
        r"\(source:Entity\)-\[source_resolution:RESOLVES_TO\]\s*->",
        compact,
    )
    assert re.search(r"\(target\)-\[target_resolution:RESOLVES_TO\]\s*->", compact)
    assert "source_resolution.source_document_id = source.document_id" in compact
    assert "target_resolution.source_document_id = target.document_id" in compact
    assert "selected_chunk.document_id = selected_document.document_id" in compact
    assert "selected_source.document_id = selected_document.document_id" in compact
    assert "source_canonical.canonical_id = seed_canonical.canonical_id" in compact
    assert "source.document_id = target.document_id" in compact
    assert "source.resolution_status IS NULL" in compact
    assert "target.resolution_status IS NULL" in compact
    assert "chunk_id: source_resolution.evidence_chunk_id" in compact
    assert "chunk_id: target_resolution.evidence_chunk_id" in compact
    assert "chunk_id: relation.evidence_chunk_id" in compact
    assert "(relation_evidence)-[:MENTIONS]->(source)" in compact
    assert "(relation_evidence)-[:MENTIONS]->(target)" in compact
    assert "source_canonical.canonical_id <> target_canonical.canonical_id" in compact
    assert not re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE)\b", _EXPAND, re.I)


def test_accepted_rows_aggregate_stably_with_bounded_provenance():
    rows = [
        _fact(
            document_id="doc-b",
            chunk_id="doc-b#2",
            source_entity_id="doc-b::alpha",
            target_entity_id="doc-b::beta",
            confidence=0.7,
        ),
        _fact(
            document_id="doc-a",
            chunk_id="doc-a#1",
            source_entity_id="doc-a::alpha",
            target_entity_id="doc-a::beta",
            confidence=0.9,
        ),
        # Duplicate rows must not inflate support.
        _fact(
            document_id="doc-a",
            chunk_id="doc-a#1",
            source_entity_id="doc-a::alpha",
            target_entity_id="doc-a::beta",
            confidence=0.9,
        ),
        _fact("canonical:b", "canonical:a", "uses", chunk_id="doc-a#2"),
        _fact("canonical:a", "canonical:b", "depends_on", chunk_id="doc-a#3"),
        # Defensive aggregation also rejects a canonical self relation.
        _fact("canonical:a", "canonical:a", "alias_of", chunk_id="doc-a#4"),
    ]

    first = expand_entities(FakeDriver(rows), ["doc-b#2", "doc-a#1"])
    second = expand_entities(FakeDriver(list(reversed(rows))), ["doc-a#1", "doc-b#2"])

    assert first == second
    assert len(first.paths) == 3
    assert len({path.path_id for path in first.paths}) == 3
    assert {(path.source_canonical_id, path.target_canonical_id, path.type) for path in first.paths} == {
        ("canonical:a", "canonical:b", "uses"),
        ("canonical:b", "canonical:a", "uses"),
        ("canonical:a", "canonical:b", "depends_on"),
    }
    uses = next(
        path
        for path in first.paths
        if (path.source_canonical_id, path.target_canonical_id, path.type)
        == ("canonical:a", "canonical:b", "uses")
    )
    assert uses.support_count == 2
    assert uses.evidence_chunk_id == "doc-a#1"
    assert [item.document_id for item in uses.provenance] == ["doc-a", "doc-b"]
    assert uses.provenance_truncated is False

    many = [
        _fact(
            document_id=f"doc-{index}",
            chunk_id=f"doc-{index}#0",
            source_entity_id=f"doc-{index}::a",
            target_entity_id=f"doc-{index}::b",
        )
        for index in range(8)
    ]
    bounded = expand_entities(FakeDriver(many), ["seed#0"]).paths[0]
    assert bounded.support_count == 8
    assert len(bounded.provenance) == 5
    assert bounded.provenance_truncated is True


def test_expand_passes_only_normalized_chunk_ids_and_uses_requested_database():
    driver = FakeDriver([])

    assert expand_entities(driver, ["b#0", "a#0", "b#0"], database="qa") == RetrievalContext(paths=[])

    assert len(driver.calls) == 1
    _, params = driver.calls[0]
    assert params == {"chunk_ids": ["a#0", "b#0"], "database_": "qa"}


def test_defensive_aggregation_rejects_malformed_fact_rows():
    malformed = [
        _fact(source="", chunk_id="doc-a#0"),
        _fact(target="", chunk_id="doc-a#0"),
        _fact(relation_type="", chunk_id="doc-a#0"),
        _fact(source="canonical:a", target="canonical:a", chunk_id="doc-a#0"),
        _fact(chunk_id=""),
        {**_fact(), "document_id": ""},
        {**_fact(), "source_entity_id": ""},
        {**_fact(), "target_entity_id": ""},
        {**_fact(), "confidence": "not-a-number"},
    ]

    assert expand_entities(FakeDriver(malformed), ["seed#0"]).paths == []


def test_agent_rejects_stale_model_chunk_ids_before_the_graph_query(monkeypatch):
    queried: list[list[str]] = []

    def _expand(driver, chunk_ids, *, database):
        queried.append(chunk_ids)
        return RetrievalContext(paths=[])

    monkeypatch.setattr(agent_mod, "expand_entities", _expand)
    evidence_pool = {"known#0": _hit("known#0")}

    invalid = agent_mod._dispatch_tool(
        "expand_entity",
        {"chunk_ids": ["stale#0"]},
        None,
        top_k=10,
        rerank_top_n=5,
        database="neo4j",
        evidence_pool=evidence_pool,
        paths_acc=[],
    )
    assert queried == []
    assert "invalid" in invalid.lower()
    assert "evidence" in invalid.lower()

    mixed = agent_mod._dispatch_tool(
        "expand_entity",
        {"chunk_ids": ["stale#0", "known#0", "known#0"]},
        None,
        top_k=10,
        rerank_top_n=5,
        database="neo4j",
        evidence_pool=evidence_pool,
        paths_acc=[],
    )
    assert queried == [["known#0"]]
    assert "ignored" in mixed.lower()


def test_agent_merges_same_canonical_path_across_tool_calls(monkeypatch):
    results = iter(
        [
            RetrievalContext(paths=[_path("doc-a", "doc-a#0")]),
            # Retrying the same observation must not inflate support.
            RetrievalContext(paths=[_path("doc-a", "doc-a#0")]),
            RetrievalContext(paths=[_path("doc-b", "doc-b#0")]),
        ]
    )
    monkeypatch.setattr(
        agent_mod,
        "expand_entities",
        lambda *args, **kwargs: next(results),
    )
    evidence_pool = {
        "doc-a#0": _hit("doc-a#0"),
        "doc-b#0": _hit("doc-b#0"),
    }
    paths: list[RelationPath] = []

    for chunk_id in ("doc-a#0", "doc-a#0", "doc-b#0"):
        agent_mod._dispatch_tool(
            "expand_entity",
            {"chunk_ids": [chunk_id]},
            None,
            top_k=10,
            rerank_top_n=5,
            database="neo4j",
            evidence_pool=evidence_pool,
            paths_acc=paths,
        )

    assert len(paths) == 1
    assert paths[0].support_count == 2
    assert [item.document_id for item in paths[0].provenance] == ["doc-a", "doc-b"]
