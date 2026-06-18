"""text_parser 测试：分段、偏移、空文件。"""

from app.parsing.text_parser import parse_text


def test_parse_text_splits_on_blank_lines(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("第一段内容。\n\n第二段内容。", encoding="utf-8")
    raw, blocks = parse_text(str(p))
    assert len(blocks) == 2
    assert blocks[0].text == "第一段内容。"
    assert blocks[1].text == "第二段内容。"


def test_parse_text_offsets_traceable(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("AAA\n\nBBB", encoding="utf-8")
    raw, blocks = parse_text(str(p))
    for b in blocks:
        assert raw[b.char_start:b.char_end] == b.text


def test_parse_text_no_page_no_heading(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("only one paragraph", encoding="utf-8")
    raw, blocks = parse_text(str(p))
    assert blocks[0].page is None
    assert blocks[0].heading_path == []


def test_parse_text_empty_file(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("", encoding="utf-8")
    raw, blocks = parse_text(str(p))
    assert raw == ""
    assert blocks == []
