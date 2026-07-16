import json

import pytest

from app.resolution import backfill
from app.resolution.models import SourceEntityRecord


class FakeStore:
    def __init__(self, driver, database="neo4j"):
        self.sources = getattr(driver, "sources", [])
        driver.store = self
        self.cleanup = 0
        self.scoped_cleanup = []

    def load_source_entities(self):
        return self.sources

    def remove_orphan_canonicals(self, canonical_ids):
        self.scoped_cleanup.append(sorted(canonical_ids))

    def remove_all_orphan_canonicals(self):
        self.cleanup += 1


class FakeDriver:
    def __init__(self):
        self.sources = [
            SourceEntityRecord(
                entity_id="doc::neo4j",
                name="Neo4j",
                entity_type="database",
                normalized_name="neo4j",
                document_id="doc",
                mention_chunk_ids=["chunk"],
            )
        ]


def test_backfill_reads_explicit_source_records_and_cleans_orphans(monkeypatch):
    driver = FakeDriver()
    captured = {}
    monkeypatch.setattr(backfill, "CanonicalOverlayStore", FakeStore)

    def fake_resolve(d, records, **kwargs):
        captured["driver"] = d
        captured["records"] = list(records)
        captured["store"] = kwargs["store"]
        return "result"

    monkeypatch.setattr(backfill, "resolve_source_entities", fake_resolve)

    result = backfill.backfill_canonical_overlay(driver)

    assert result == "result"
    assert captured["records"][0].document_id == "doc"
    assert captured["store"].cleanup == 1
    assert captured["store"].scoped_cleanup == []


def test_alias_jsonl_requires_full_provenance(tmp_path):
    path = tmp_path / "aliases.jsonl"
    path.write_text(
        json.dumps(
            {
                "alias": "PG",
                "canonical_id": "canonical:postgresql",
                "source_entity_id": "doc::pg",
                "source_document_id": "doc",
                "source_chunk_id": "chunk",
            }
        ),
        encoding="utf-8",
    )

    records = backfill.load_alias_jsonl(path)

    assert records[0].source_chunk_id == "chunk"

    path.write_text('{"alias":"PG","canonical_id":"canonical:postgresql"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        backfill.load_alias_jsonl(path)
