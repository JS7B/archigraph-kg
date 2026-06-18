"""txt 解析：按连续空行分段，记录真实字符偏移。"""

import re

from app.parsing.models import Block

# 连续空行（含只有空白的行）作为段落分隔
_PARA_SPLIT = re.compile(r"\n[ \t]*\n")


def parse_text(path: str) -> tuple[str, list[Block]]:
    """读取 txt 文件，返回 (raw_text, blocks)。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw_text = f.read()

    blocks: list[Block] = []
    pos = 0
    for part in _PARA_SPLIT.split(raw_text):
        start = raw_text.find(part, pos)
        if part.strip() == "":
            pos = start + len(part)
            continue
        # 去掉段首尾空白后定位真实区间
        stripped = part.strip()
        real_start = raw_text.find(stripped, start)
        real_end = real_start + len(stripped)
        blocks.append(
            Block(text=stripped, char_start=real_start, char_end=real_end)
        )
        pos = real_end
    return raw_text, blocks
