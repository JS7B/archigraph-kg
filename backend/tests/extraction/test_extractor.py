"""extract_document：有限并发、顺序恢复与失败隔离。"""

import threading

import pytest

from app.extraction import extractor
from app.extraction.errors import ExtractionError
from app.extraction.merge import merge_extractions
from app.extraction.models import (
    ChunkExtractionResult,
    Evidence,
    ExtractedEntity,
)
from app.parsing.models import Chunk, ExtractionPolicy, ParsedDocument, SourceLocation


def _doc(n: int) -> ParsedDocument:
    return _doc_with_indices(list(range(n)))


def _doc_with_indices(indices: list[int]) -> ParsedDocument:
    chunks = [
        Chunk(
            chunk_index=i,
            text=f"chunk {i}",
            location=SourceLocation(document_id="test_d", char_start=i, char_end=i + 1),
            char_count=1,
        )
        for i in indices
    ]
    return ParsedDocument(
        document_id="test_d", source_path="x", doc_type="text", raw_text="x", chunks=chunks
    )


def test_partial_failure_recorded(monkeypatch):
    def fake_extract(chunk_id, text, **kwargs):
        if chunk_id == "test_d#1":
            raise ExtractionError(chunk_id=chunk_id, reason="boom")
        return ChunkExtractionResult(entities=[], relations=[])

    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)
    extractions, failures = extractor.extract_document(_doc(3))
    assert len(extractions) == 2
    assert len(failures) == 1
    assert failures[0].chunk_id == "test_d#1"


@pytest.mark.parametrize(
    ("max_workers", "expected_peak"),
    [(None, 3), (2, 2)],
)
def test_extraction_is_bounded_and_really_overlaps(
    monkeypatch, max_workers, expected_peak
):
    active = 0
    peak = 0
    lock = threading.Lock()
    enough_started = threading.Event()
    release = threading.Event()
    outcome = {}
    progress = []

    def fake_extract(*args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == expected_peak:
                enough_started.set()
        release.wait()
        with lock:
            active -= 1
        return ChunkExtractionResult()

    def run_extraction():
        try:
            kwargs = {} if max_workers is None else {"max_workers": max_workers}
            outcome["result"] = extractor.extract_document(
                _doc(5),
                on_progress=lambda completed, total: progress.append(
                    (completed, total)
                ),
                **kwargs,
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            outcome["error"] = exc

    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)
    worker = threading.Thread(target=run_extraction, daemon=True)
    worker.start()
    try:
        assert enough_started.wait(timeout=2), "extract_chunk calls did not overlap"
        assert progress == []
    finally:
        release.set()
        worker.join(timeout=2)

    assert not worker.is_alive()
    assert "error" not in outcome
    assert peak == expected_peak
    assert len(outcome["result"][0]) == 5
    assert progress == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


def test_out_of_order_completion_restores_document_order_before_merge(monkeypatch):
    later_success_done = threading.Event()
    later_failure_done = threading.Event()
    progress = []
    coordinator_thread = threading.get_ident()
    progress_threads = []

    def fake_extract(chunk_id, text, **kwargs):
        if chunk_id == "test_d#2":
            assert later_success_done.wait(timeout=2)
            return ChunkExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="Order Sensitive",
                        type="概念",
                        evidence=Evidence(chunk_id=chunk_id, text=text),
                    )
                ]
            )
        if chunk_id == "test_d#11":
            later_success_done.set()
            return ChunkExtractionResult(
                entities=[
                    ExtractedEntity(
                        name="Order Sensitive",
                        type="技术",
                        evidence=Evidence(chunk_id=chunk_id, text=text),
                    )
                ]
            )
        if chunk_id == "test_d#3":
            assert later_failure_done.wait(timeout=2)
            raise ExtractionError(chunk_id=chunk_id, reason="source failure")
        later_failure_done.set()
        raise ExtractionError(chunk_id=chunk_id, reason="later failure")

    def record_progress(completed, total):
        progress.append((completed, total))
        progress_threads.append(threading.get_ident())

    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)
    extractions, failures = extractor.extract_document(
        _doc_with_indices([2, 11, 3, 10]),
        max_workers=4,
        on_progress=record_progress,
    )

    # Completion and lexical chunk-id order are both the reverse of source order.
    assert [item.chunk_id for item in extractions] == ["test_d#2", "test_d#11"]
    assert [item.chunk_id for item in failures] == ["test_d#3", "test_d#10"]
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert progress_threads == [coordinator_thread] * 4
    # merge_extractions resolves a type tie by first-seen order, so this assertion
    # guards the graph semantics rather than only the extractor list shape.
    merged = merge_extractions("test_d", extractions)
    assert merged.entities[0].type == "概念"


def test_unexpected_exception_fails_the_document(monkeypatch):
    other_started = threading.Event()
    unexpected_raised = threading.Event()
    release_other = threading.Event()
    outcome = {}

    def fake_extract(chunk_id, *args, **kwargs):
        if chunk_id == "test_d#0":
            assert other_started.wait(timeout=2)
            unexpected_raised.set()
            raise RuntimeError("unexpected")
        other_started.set()
        release_other.wait()
        return ChunkExtractionResult()

    def run_extraction():
        try:
            extractor.extract_document(_doc(2), max_workers=2)
        except BaseException as exc:  # pragma: no cover - surfaced below
            outcome["error"] = exc

    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)
    worker = threading.Thread(target=run_extraction, daemon=True)
    worker.start()
    try:
        assert unexpected_raised.wait(timeout=2)
        # The coordinator must leave the executor context and join the other
        # running future before surfacing the unexpected exception.
        assert worker.is_alive()
    finally:
        release_other.set()
        worker.join(timeout=2)

    assert not worker.is_alive()
    assert isinstance(outcome.get("error"), RuntimeError)
    assert str(outcome["error"]) == "unexpected"


def test_extraction_arguments_are_preserved(monkeypatch):
    calls = {}

    def fake_extract(chunk_id, text, **kwargs):
        calls[chunk_id] = kwargs
        return ChunkExtractionResult()

    doc = _doc(2)
    doc.chunks[0].extraction_policy = ExtractionPolicy.SPECIALIZED
    doc.chunks[0].language = "python"
    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)

    extractor.extract_document(doc, max_attempts=7)

    assert calls["test_d#0"] == {
        "max_attempts": 7,
        "extraction_policy": ExtractionPolicy.SPECIALIZED,
        "language": "python",
    }
    assert calls["test_d#1"] == {"max_attempts": 7}


def test_skip_chunk_does_not_call_llm_or_create_extraction(monkeypatch):
    calls = []

    def fake_extract(*args, **kwargs):
        calls.append((args, kwargs))
        return ChunkExtractionResult(entities=[], relations=[])

    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)
    doc = _doc(1)
    doc.chunks[0].extraction_policy = ExtractionPolicy.SKIP

    progress = []
    extractions, failures = extractor.extract_document(
        doc, on_progress=lambda completed, total: progress.append((completed, total))
    )

    assert calls == []
    assert extractions == []
    assert failures == []
    assert progress == []


def test_skip_chunks_are_excluded_from_progress_total(monkeypatch):
    monkeypatch.setattr(
        extractor, "extract_chunk", lambda *args, **kwargs: ChunkExtractionResult()
    )
    doc = _doc(3)
    doc.chunks[1].extraction_policy = ExtractionPolicy.SKIP
    progress = []

    extractor.extract_document(
        doc, on_progress=lambda completed, total: progress.append((completed, total))
    )

    assert progress == [(1, 2), (2, 2)]
