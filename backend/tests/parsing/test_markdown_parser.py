"""markdown_parser 测试：标题路径、偏移、标题不重复。"""

from app.parsing.markdown_parser import parse_markdown


def test_heading_path_tracks_hierarchy(tmp_path):
    md = "# 安装\n\n安装说明。\n\n## 依赖\n\n依赖说明。"
    p = tmp_path / "a.md"
    p.write_text(md, encoding="utf-8")
    raw, blocks = parse_markdown(str(p))
    # 找到含「依赖说明」的块，其 heading_path 应为 ["安装", "依赖"]
    dep = [b for b in blocks if "依赖说明" in b.text][0]
    assert dep.heading_path == ["安装", "依赖"]


def test_offsets_traceable(tmp_path):
    md = "# A\n\n正文一。\n\n## B\n\n正文二。"
    p = tmp_path / "a.md"
    p.write_text(md, encoding="utf-8")
    raw, blocks = parse_markdown(str(p))
    for b in blocks:
        assert raw[b.char_start:b.char_end] == b.text


def test_heading_text_not_duplicated(tmp_path):
    md = "# 唯一标题\n\n正文。"
    p = tmp_path / "a.md"
    p.write_text(md, encoding="utf-8")
    raw, blocks = parse_markdown(str(p))
    # 「唯一标题」在所有 block.text 拼接中只出现一次
    joined = "".join(b.text for b in blocks)
    assert joined.count("唯一标题") == 1


def test_no_page(tmp_path):
    md = "# A\n\n正文。"
    p = tmp_path / "a.md"
    p.write_text(md, encoding="utf-8")
    raw, blocks = parse_markdown(str(p))
    assert all(b.page is None for b in blocks)


def test_sibling_heading_pops_stack(tmp_path):
    md = "## 第一节\n\n甲。\n\n## 第二节\n\n乙。"
    p = tmp_path / "a.md"
    p.write_text(md, encoding="utf-8")
    raw, blocks = parse_markdown(str(p))
    second = [b for b in blocks if "乙" in b.text][0]
    assert second.heading_path == ["第二节"]
