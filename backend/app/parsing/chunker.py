"""chunker：把 Block 列表聚合成目标大小的 Chunk，保持同页同标题边界。

偏移与 text 一致性：chunk.text 一律取 raw_text[start:end]，保证
raw_text[chunk.char_start:chunk.char_end] == chunk.text。

超长 Block 由 chunk_blocks 内部先调 split_oversized_block 预拆，再做聚合——
调用方无需自己预拆。

不做小块回填：贪心聚合已用「适配 max_chars 且同页同标题」合并所有能合并的相邻块；
跨页/跨标题的微小尾块不回填（回填会污染 provenance），是 provenance 优先的有意产物。
"""

import logging

from app.parsing.models import Block, Chunk, SourceLocation

logger = logging.getLogger(__name__)

MAX_CHARS = 800
OVERLAP_CHARS = 150

_BREAKPOINTS = ("。", ".", "\n", " ")


def _find_breakpoint(text: str, window_end: int, window_start: int) -> int:
    """Return the best cut point in [window_start, window_end).

    Searches for the last natural breakpoint within the window and returns
    the position right after it (so the breakpoint char is included in the
    current chunk).  Returns window_end when no breakpoint is found (hard cut).
    """
    for bp in _BREAKPOINTS:
        idx = text.rfind(bp, window_start, window_end)
        if idx != -1:
            return idx + 1
    return window_end


def split_oversized_block(
    block: Block,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[Block]:
    """Split an oversized Block into sub-blocks via sliding window.

    Each window is at most *max_chars* wide; consecutive windows overlap by
    *overlap_chars*.  The cut point prefers a natural breakpoint (句号, period,
    newline, space) and falls back to a hard cut at max_chars.

    Sub-block char_start/end are recalculated relative to the parent block's
    char_start so offsets remain traceable to the original raw_text.
    """
    text = block.text
    if len(text) <= max_chars:
        return [block]

    subs: list[Block] = []
    pos = 0
    n = len(text)
    while pos < n:
        window_end = min(pos + max_chars, n)
        if window_end < n:
            cut = _find_breakpoint(text, window_end, pos + 1)
        else:
            cut = window_end
        sub_text = text[pos:cut]
        subs.append(
            Block(
                text=sub_text,
                char_start=block.char_start + pos,
                char_end=block.char_start + cut,
                page=block.page,
                heading_path=block.heading_path,
            )
        )
        if cut >= n:
            break
        pos = max(cut - overlap_chars, pos + 1)
    return subs


def _make_chunk(index: int, group: list[Block], document_id: str, raw_text: str) -> Chunk:
    start = group[0].char_start
    end = group[-1].char_end
    text = raw_text[start:end]
    loc = SourceLocation(
        document_id=document_id,
        char_start=start,
        char_end=end,
        page=group[0].page,
        heading_path=group[0].heading_path,
    )
    return Chunk(chunk_index=index, text=text, location=loc, char_count=len(text))


def _same_boundary(a: Block, b: Block) -> bool:
    return a.page == b.page and a.heading_path == b.heading_path


def chunk_blocks(
    blocks: list[Block],
    document_id: str,
    raw_text: str,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[Chunk]:
    """把 Block 列表聚合成 Chunk 列表。

    聚合：相邻块在「累积长度 + 下一块 <= max_chars」且同页同标题时合并进同一 chunk；
    否则收尾当前 chunk、另起一个。
    """
    if not blocks:
        return []

    # Step 1: pre-split oversized blocks
    expanded: list[Block] = []
    for block in blocks:
        expanded.extend(split_oversized_block(block, max_chars, overlap_chars))
    blocks = expanded

    groups: list[list[Block]] = []
    current: list[Block] = [blocks[0]]
    current_len = len(blocks[0].text)
    for block in blocks[1:]:
        fits = current_len + len(block.text) <= max_chars
        if fits and _same_boundary(current[-1], block):
            current.append(block)
            current_len += len(block.text)
        else:
            groups.append(current)
            current = [block]
            current_len = len(block.text)
    groups.append(current)

    return [
        _make_chunk(i, group, document_id, raw_text)
        for i, group in enumerate(groups)
    ]
