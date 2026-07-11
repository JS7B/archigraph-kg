"""parsing 数据模型与异常的基础测试。"""

import pytest

from app.parsing.models import (
    Block,
    Chunk,
    ContentKind,
    ExtractionPolicy,
    ParsedDocument,
    SourceLocation,
)
from app.parsing.errors import ParseError


def test_source_location_defaults():
    loc = SourceLocation(document_id="doc1", char_start=0, char_end=10)
    assert loc.page is None
    assert loc.heading_path == []


def test_block_holds_offsets_and_provenance():
    block = Block(text="hello", char_start=3, char_end=8, page=2, heading_path=["A", "B"])
    assert block.char_end - block.char_start == 5
    assert block.page == 2
    assert block.heading_path == ["A", "B"]


def test_block_and_chunk_content_metadata_defaults():
    block = Block(text="hello", char_start=0, char_end=5)
    chunk = Chunk(
        chunk_index=0,
        text="hello",
        location=SourceLocation(document_id="doc1", char_start=0, char_end=5),
        char_count=5,
    )

    assert block.content_kind is ContentKind.PROSE
    assert block.language is None
    assert block.extraction_policy is ExtractionPolicy.NORMAL
    assert chunk.content_kind is ContentKind.PROSE
    assert chunk.language is None
    assert chunk.extraction_policy is ExtractionPolicy.NORMAL


def test_block_and_chunk_accept_explicit_code_metadata():
    metadata = {
        "content_kind": ContentKind.CODE,
        "language": "python",
        "extraction_policy": ExtractionPolicy.SPECIALIZED,
    }
    block = Block(text="print('hi')", char_start=0, char_end=11, **metadata)
    chunk = Chunk(
        chunk_index=0,
        text="print('hi')",
        location=SourceLocation(document_id="doc1", char_start=0, char_end=11),
        char_count=11,
        **metadata,
    )

    assert block.content_kind is ContentKind.CODE
    assert block.language == "python"
    assert block.extraction_policy is ExtractionPolicy.SPECIALIZED
    assert chunk.content_kind is ContentKind.CODE
    assert chunk.language == "python"
    assert chunk.extraction_policy is ExtractionPolicy.SPECIALIZED


def test_content_metadata_serializes_to_values():
    block = Block(
        text="port: 8000",
        char_start=0,
        char_end=10,
        content_kind=ContentKind.CONFIG,
        language="yaml",
        extraction_policy=ExtractionPolicy.SKIP,
    )

    assert block.model_dump(mode="json")["content_kind"] == "config"
    assert block.model_dump(mode="json")["language"] == "yaml"
    assert block.model_dump(mode="json")["extraction_policy"] == "skip"


def test_chunk_carries_location():
    loc = SourceLocation(document_id="doc1", char_start=0, char_end=5, page=1)
    chunk = Chunk(chunk_index=0, text="hello", location=loc, char_count=5)
    assert chunk.chunk_index == 0
    assert chunk.location.page == 1


def test_parsed_document_holds_chunks():
    doc = ParsedDocument(
        document_id="doc1",
        source_path="/tmp/doc1.txt",
        doc_type="text",
        raw_text="hello world",
        chunks=[],
    )
    assert doc.doc_type == "text"
    assert doc.chunks == []


def test_parse_error_message_contains_path_and_reason():
    err = ParseError(path="/tmp/bad.xyz", reason="unsupported extension")
    assert "/tmp/bad.xyz" in str(err)
    assert "unsupported extension" in str(err)
