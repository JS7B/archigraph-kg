"""Internal CLI for idempotently backfilling the canonical overlay."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from neo4j import Driver

from app.clients.graph import close, get_driver
from app.graph.schema import ensure_schema
from app.resolution.models import AliasRecord, CanonicalizationResult
from app.resolution.persistence import CanonicalOverlayStore
from app.resolution.service import resolve_source_entities


def load_alias_jsonl(path: str | Path) -> list[AliasRecord]:
    records: list[AliasRecord] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(AliasRecord.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid alias JSONL line {line_number}: {exc}") from exc
    return records


def backfill_canonical_overlay(
    driver: Driver,
    *,
    aliases: Iterable[AliasRecord] = (),
    database: str = "neo4j",
) -> CanonicalizationResult:
    """Resolve all source entities without reparsing, LLMs, or source rewrites."""

    store = CanonicalOverlayStore(driver, database=database)
    sources = store.load_source_entities()
    result = resolve_source_entities(
        driver,
        sources,
        aliases=aliases,
        database=database,
        store=store,
    )
    store.remove_orphan_canonicals()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill canonical entity overlay")
    parser.add_argument("--aliases", help="optional provenance-carrying alias JSONL")
    args = parser.parse_args(argv)
    aliases = load_alias_jsonl(args.aliases) if args.aliases else []
    driver = get_driver()
    try:
        ensure_schema(driver)
        result = backfill_canonical_overlay(driver, aliases=aliases)
    finally:
        close(driver)
    print(
        "canonical overlay: "
        f"accepted={result.accepted_count}, review={result.review_count}, "
        f"unresolved={result.unresolved_count}, bootstrapped={result.bootstrap_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
