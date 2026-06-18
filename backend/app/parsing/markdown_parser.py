"""Markdown 解析：纯文本扫描维护标题栈，不引渲染库。

raw_text 保留原始全文（含标题语法），保证偏移可追溯。
标题行与其后正文合为同一 Block，标题文字不重复出现。
"""

import re

from app.parsing.models import Block

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_PARA_SPLIT = re.compile(r"\n[ \t]*\n")


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
    pos = 0
    for part in _PARA_SPLIT.split(raw_text):
        if part.strip() == "":
            pos += len(part)
            continue
        stripped = part.strip()
        start = raw_text.find(stripped, pos)
        end = start + len(stripped)
        heading_path = _heading_path_at(raw_text, start + 1)
        blocks.append(
            Block(
                text=stripped,
                char_start=start,
                char_end=end,
                heading_path=heading_path,
            )
        )
        pos = end
    return raw_text, blocks
