"""chunker 测试：聚合、同页同标题守卫、小块回填、偏移可追溯。"""

from app.parsing.chunker import chunk_blocks, MAX_CHARS, split_oversized_block
from app.parsing.models import Block


def _block(text, start, page=None, heading=None):
    return Block(
        text=text,
        char_start=start,
        char_end=start + len(text),
        page=page,
        heading_path=heading or [],
    )


def test_small_adjacent_blocks_merge_into_one_chunk():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0), _block("BBB", 5)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 1
    assert chunks[0].location.char_start == 0
    assert chunks[0].location.char_end == 8
    assert chunks[0].text == raw[0:8]


def test_offset_is_traceable_to_raw_text():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0), _block("BBB", 5)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    for c in chunks:
        assert raw[c.location.char_start:c.location.char_end] == c.text


def test_different_page_does_not_merge():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0, page=1), _block("BBB", 5, page=2)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 2
    assert chunks[0].location.page == 1
    assert chunks[1].location.page == 2


def test_different_heading_does_not_merge():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0, heading=["X"]), _block("BBB", 5, heading=["Y"])]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 2


def test_chunk_index_is_sequential():
    raw = "AAA\n\nBBB"
    blocks = [_block("AAA", 0, page=1), _block("BBB", 5, page=2)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_small_trailing_block_same_boundary_merges():
    # 同页同标题、合计 <= max_chars 的尾块在聚合阶段就并入，不另起 chunk
    raw = "A" * 700 + "\n\n" + "B" * 10
    blocks = [_block("A" * 700, 0), _block("B" * 10, 702)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 1
    assert chunks[0].location.char_end == 712


def test_small_trailing_block_cross_boundary_stays_separate():
    # 跨页的微小尾块不回填，保留为独立小 chunk（provenance 优先的有意产物）
    raw = "A" * 700 + "\n\n" + "B" * 10
    blocks = [_block("A" * 700, 0, page=1), _block("B" * 10, 702, page=2)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 2
    assert chunks[1].location.page == 2


def test_empty_blocks_returns_empty():
    assert chunk_blocks([], document_id="d", raw_text="") == []


def test_split_oversized_block_produces_multiple_subblocks():
    text = "x" * 2000
    block = Block(text=text, char_start=0, char_end=2000)
    subs = split_oversized_block(block, max_chars=800, overlap_chars=150)
    assert len(subs) >= 3
    # sub-block offsets must round-trip to parent text
    for s in subs:
        assert text[s.char_start:s.char_end] == s.text


def test_split_oversized_block_overlaps():
    text = "x" * 2000
    block = Block(text=text, char_start=0, char_end=2000)
    subs = split_oversized_block(block, max_chars=800, overlap_chars=150)
    # second block starts before first block ends (overlap exists)
    assert subs[1].char_start < subs[0].char_end


def test_split_prefers_natural_breakpoint():
    # period at position 600, window of 800 should cut right after it
    text = "A" * 600 + "." + "B" * 800
    block = Block(text=text, char_start=0, char_end=len(text))
    subs = split_oversized_block(block, max_chars=800, overlap_chars=150)
    # first sub-block should end with period
    assert subs[0].text.endswith(".")


def test_chunk_blocks_splits_oversized_then_aggregates():
    raw = "x" * 2000
    block = Block(text=raw, char_start=0, char_end=2000)
    chunks = chunk_blocks([block], document_id="d", raw_text=raw)
    assert len(chunks) >= 3
    for c in chunks:
        assert raw[c.location.char_start:c.location.char_end] == c.text


def test_block_not_oversized_returns_single():
    text = "short"
    block = Block(text=text, char_start=10, char_end=15)
    subs = split_oversized_block(block, max_chars=800)
    assert len(subs) == 1
    assert subs[0].char_start == 10
    assert subs[0].char_end == 15
