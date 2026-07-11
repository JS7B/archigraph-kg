"""Markdown 解析：纯文本扫描维护标题栈，不引渲染库。

raw_text 保留原始全文（含标题语法），保证偏移可追溯。
标题行与其后正文合为同一 Block，标题文字不重复出现。
"""

import re

from app.parsing.content_classifier import classify_block
from app.parsing.models import Block

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_PARA_SPLIT = re.compile(r"\n[ \t]*\n")
_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<marker>`{3,}|~{3,})(?P<info>.*)$")


def _heading_path_at(raw_text: str, upto: int) -> list[str]:
    """计算位置 upto 处生效的标题栈快照。"""
    stack: list[tuple[int, str]] = []  # (level, title)
    for m in re.finditer(r"^(#{1,6})\s+(.*)$", raw_text[:upto], re.MULTILINE):
        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
    return [t for _, t in stack]


def parse_markdown(path: str) -> tuple[str, list[Block]]:
    """读取 Markdown，返回 (raw_text, blocks)。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw_text = f.read()

    blocks: list[Block] = []

    def append_plain(start: int, end: int) -> None:
        pos = start
        for separator in _PARA_SPLIT.finditer(raw_text, start, end):
            append_plain_part(pos, separator.start())
            pos = separator.end()
        append_plain_part(pos, end)

    def append_plain_part(start: int, end: int) -> None:
        part = raw_text[start:end]
        if part.strip() == "":
            return
        stripped = part.strip()
        block_start = start + len(part) - len(part.lstrip())
        block_end = block_start + len(stripped)
        kind, language, policy = classify_block(stripped)
        blocks.append(
            Block(
                text=stripped,
                char_start=block_start,
                char_end=block_end,
                heading_path=_heading_path_at(raw_text, block_start + 1),
                content_kind=kind,
                language=language,
                extraction_policy=policy,
            )
        )

    spans: list[tuple[int, int, str]] = []
    lines = raw_text.splitlines(keepends=True)
    offset = 0
    open_start: int | None = None
    open_marker: str | None = None
    open_info = ""
    for line in lines:
        content = line.rstrip("\r\n")
        match = _FENCE_OPEN.match(content)
        if open_start is None:
            if match:
                open_start = offset
                open_marker = match.group("marker")
                open_info = match.group("info").strip()
        elif (
            match
            and match.group("marker")[0] == open_marker[0]
            and len(match.group("marker")) >= len(open_marker)
            and not match.group("info").strip()
        ):
            # Keep the closing marker itself in the block, but leave its line
            # ending for the following plain-text span. This keeps offsets
            # traceable without swallowing the next paragraph.
            end = offset + len(content)
            spans.append((open_start, end, open_info))
            open_start = None
            open_marker = None
            open_info = ""
        offset += len(line)
    if open_start is not None:
        spans.append((open_start, len(raw_text), open_info))

    cursor = 0
    for start, end, info in spans:
        append_plain(cursor, start)
        kind, language, policy = classify_block(raw_text[start:end], fenced_language=info)
        blocks.append(
            Block(
                text=raw_text[start:end],
                char_start=start,
                char_end=end,
                heading_path=_heading_path_at(raw_text, start + 1),
                content_kind=kind,
                language=language,
                extraction_policy=policy,
            )
        )
        cursor = end
    append_plain(cursor, len(raw_text))
    return raw_text, blocks
