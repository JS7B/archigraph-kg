"""extract_document：部分 chunk 失败记入 failures，其余正常。"""

from app.extraction import extractor
from app.extraction.errors import ExtractionError
from app.extraction.models import ChunkExtractionResult
from app.parsing.models import Chunk, ExtractionPolicy, ParsedDocument, SourceLocation


def _doc(n: int) -> ParsedDocument:
    chunks = [
        Chunk(
            chunk_index=i,
            text=f"chunk {i}",
            location=SourceLocation(document_id="test_d", char_start=i, char_end=i + 1),
            char_count=1,
        )
        for i in range(n)
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


def test_skip_chunk_does_not_call_llm_or_create_extraction(monkeypatch):
    calls = []

    def fake_extract(*args, **kwargs):
        calls.append((args, kwargs))
        return ChunkExtractionResult(entities=[], relations=[])

    monkeypatch.setattr(extractor, "extract_chunk", fake_extract)
    doc = _doc(1)
    doc.chunks[0].extraction_policy = ExtractionPolicy.SKIP

    extractions, failures = extractor.extract_document(doc)

    assert calls == []
    assert extractions == []
    assert failures == []
