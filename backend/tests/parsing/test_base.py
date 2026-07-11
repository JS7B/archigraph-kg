"""base 分派与 parse_file 组装测试。"""

import pytest
import app.parsing as public_parsing

from app.parsing.base import parse_file
from app.parsing.errors import ParseError
from app.parsing.models import ContentKind, ExtractionPolicy


def test_parse_file_txt(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("第一段。\n\n第二段。", encoding="utf-8")
    doc = parse_file(str(p))
    assert doc.doc_type == "text"
    assert doc.document_id == "doc.txt"
    assert len(doc.chunks) >= 1


def test_parse_file_markdown(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# 标题\n\n正文内容。", encoding="utf-8")
    doc = parse_file(str(p))
    assert doc.doc_type == "markdown"


def test_parse_file_markdown_preserves_code_and_config_chunk_metadata(tmp_path):
    p = tmp_path / "doc.md"
    raw = (
        "# Example\n\n"
        "A paragraph.\n\n"
        "```python\nprint('hi')\n```\n\n"
        "```json\n{\"port\": 8000}\n```\n"
    )
    p.write_text(raw, encoding="utf-8")

    doc = parse_file(str(p))

    code_chunks = [c for c in doc.chunks if c.content_kind is ContentKind.CODE]
    config_chunks = [
        c for c in doc.chunks if c.content_kind is ContentKind.CONFIG
    ]
    assert len(code_chunks) == 1
    assert code_chunks[0].language == "python"
    assert code_chunks[0].extraction_policy is ExtractionPolicy.SPECIALIZED
    assert len(config_chunks) == 1
    assert config_chunks[0].language == "json"
    assert config_chunks[0].extraction_policy is ExtractionPolicy.SKIP
    assert all(
        doc.raw_text[c.location.char_start : c.location.char_end] == c.text
        for c in doc.chunks
    )


def test_public_parser_exposes_content_policy_metadata(tmp_path):
    p = tmp_path / "mixed.md"
    raw = (
        "# Example\n\n"
        "A paragraph.\n\n"
        "```python\nprint('hi')\n```\n\n"
        "```json\n{\"port\": 8000}\n```\n"
    )
    p.write_text(raw, encoding="utf-8")

    doc = public_parsing.parse_file(str(p))

    assert hasattr(public_parsing, "ContentKind")
    assert hasattr(public_parsing, "ExtractionPolicy")
    code_chunk = next(c for c in doc.chunks if c.content_kind.value == "code")
    config_chunk = next(c for c in doc.chunks if c.content_kind.value == "config")
    assert code_chunk.content_kind is public_parsing.ContentKind.CODE
    assert code_chunk.language == "python"
    assert code_chunk.extraction_policy is public_parsing.ExtractionPolicy.SPECIALIZED
    assert config_chunk.content_kind is public_parsing.ContentKind.CONFIG
    assert config_chunk.language == "json"
    assert config_chunk.extraction_policy is public_parsing.ExtractionPolicy.SKIP
    assert all(
        doc.raw_text[c.location.char_start : c.location.char_end] == c.text
        for c in doc.chunks
    )


def test_parse_file_chunk_offsets_traceable(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("AAA\n\nBBB", encoding="utf-8")
    doc = parse_file(str(p))
    for c in doc.chunks:
        assert doc.raw_text[c.location.char_start:c.location.char_end] == c.text


def test_parse_file_custom_document_id(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("内容", encoding="utf-8")
    doc = parse_file(str(p), document_id="custom-id")
    assert doc.document_id == "custom-id"
    assert all(c.location.document_id == "custom-id" for c in doc.chunks)


def test_parse_file_missing_raises():
    with pytest.raises(ParseError):
        parse_file("/nonexistent/path/x.txt")


def test_parse_file_unsupported_extension_raises(tmp_path):
    p = tmp_path / "doc.xyz"
    p.write_text("内容", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_file(str(p))
