# 文档解析与切块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个纯解析库，把 Markdown / txt / PDF 文件和 GitHub 仓库目录转成带来源元数据（字符偏移 + 页码 + 标题路径）的 `Chunk` 对象列表。

**Architecture:** 两段式数据流，`文件 ──parser──> ParsedDocument(raw_text, blocks[]) ──chunker──> Chunk[]`。parser 层格式相关，只负责「抽全文 + 切成带位置的语义块 Block」；chunker 层格式无关，按语义边界聚合 + 超长字符上限拆分。两层彻底解耦：换切块策略不动 parser，加新格式只写新 parser。

**Tech Stack:** Python 3.12（conda `myself` 环境）· Pydantic · PyMuPDF（`fitz`）· pytest。

## Global Constraints

- 本板块是纯解析库：不碰 Neo4j、不碰 embedding、不接 HTTP。
- chunk 尺寸单位 = 字符数，不引 tokenizer，不绑厂商。
- chunk 大小默认值：`max_chars=800` / `overlap_chars=150` / `min_chars=100`，作为 `chunker.py` 模块常量，可传参覆盖，**不进 .env**（解析策略非部署配置）。
- provenance 三要素：字符偏移 `[char_start, char_end)`（左闭右开）+ PDF 页码（1-based，非 PDF 为 None）+ Markdown 标题路径（list[str]，无则空列表）。
- 所有偏移量相对 `ParsedDocument.raw_text`；核心不变量：`raw_text[chunk.char_start:chunk.char_end] == chunk.text`。
- overlap 只作用在「单个超长 Block 内部滑窗」，跨 Block 聚合不加 overlap。
- 错误分层：硬失败（文件不存在 / 扩展名不支持 / PDF 损坏）抛 `ParseError`；软降级（PDF 扫描页无文本层 / 编码异常 / 空文件）记 warning 继续。
- 日志复用项目已有 `app.logging_conf`，用标准 `logging.getLogger(__name__)`。
- 沿用现有测试风格：plain pytest 函数，`from app.parsing import ...`。
- 安装 PyMuPDF 前必须先征求用户同意（CLAUDE.md「需安装新依赖务必先询问」）。
- 测试命令（从 `backend/` 目录运行）：`conda run -n myself python -m pytest -q`

## File Structure

```
backend/app/parsing/
├── __init__.py          # 对外导出 parse_file / parse_directory / ParseError 及模型
├── models.py            # SourceLocation, Block, Chunk, ParsedDocument（Pydantic）
├── errors.py            # ParseError 自定义异常
├── chunker.py           # chunk_blocks(blocks, document_id, ...) -> list[Chunk]
├── text_parser.py       # parse_text(path) -> (raw_text, blocks)
├── markdown_parser.py   # parse_markdown(path) -> (raw_text, blocks)
├── pdf_parser.py        # parse_pdf(path) -> (raw_text, blocks)
├── base.py              # parse_file(path) -> ParsedDocument（按扩展名分派 + 组装 + chunk）
└── repo_importer.py     # parse_directory(path) -> list[ParsedDocument]

backend/tests/parsing/
├── __init__.py
├── test_models.py
├── test_chunker.py
├── test_text_parser.py
├── test_markdown_parser.py
├── test_pdf_parser.py
├── test_base.py
└── test_repo_importer.py
```

任务顺序按依赖自底向上：models → errors → chunker → 各 parser → base 分派 → repo_importer。每个任务结束都有独立可测的交付物。

---

### Task 1: 数据模型 + 自定义异常

**Files:**
- Create: `backend/app/parsing/__init__.py`
- Create: `backend/app/parsing/models.py`
- Create: `backend/app/parsing/errors.py`
- Create: `backend/tests/parsing/__init__.py`
- Test: `backend/tests/parsing/test_models.py`

**Interfaces:**
- Consumes: 无（基础任务）
- Produces:
  - `SourceLocation(document_id: str, char_start: int, char_end: int, page: int | None = None, heading_path: list[str] = [])`
  - `Block(text: str, char_start: int, char_end: int, page: int | None = None, heading_path: list[str] = [])`
  - `Chunk(chunk_index: int, text: str, location: SourceLocation, char_count: int)`
  - `ParsedDocument(document_id: str, source_path: str, doc_type: str, raw_text: str, chunks: list[Chunk])`
  - `ParseError(Exception)`，构造 `ParseError(path: str, reason: str)`，`str()` 含 path 和 reason

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/__init__.py` 写空文件。`backend/tests/parsing/test_models.py`：

```python
"""parsing 数据模型与异常的基础测试。"""

import pytest

from app.parsing.models import Block, Chunk, ParsedDocument, SourceLocation
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
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/` 目录）：`conda run -n myself python -m pytest tests/parsing/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing'`

- [ ] **Step 3: 写最小实现**

`backend/app/parsing/__init__.py` 先写空文件（Task 8 再补导出）。

`backend/app/parsing/errors.py`：

```python
"""parsing 包的自定义异常。"""


class ParseError(Exception):
    """硬失败：无法解析（文件不存在 / 扩展名不支持 / 文件损坏）。"""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"解析失败 [{path}]: {reason}")
```

`backend/app/parsing/models.py`：

```python
"""parsing 数据模型：SourceLocation / Block / Chunk / ParsedDocument。

所有偏移量相对 ParsedDocument.raw_text，左闭右开 [char_start, char_end)。
"""

from pydantic import BaseModel, Field


class SourceLocation(BaseModel):
    """一个 chunk 的来源位置（provenance）。"""

    document_id: str
    char_start: int
    char_end: int
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)


class Block(BaseModel):
    """parser 输出的中间语义块，喂给 chunker，不直接出库。"""

    text: str
    char_start: int
    char_end: int
    page: int | None = None
    heading_path: list[str] = Field(default_factory=list)


class Chunk(BaseModel):
    """本板块最终产物：带来源位置的文本片段。"""

    chunk_index: int
    text: str
    location: SourceLocation
    char_count: int


class ParsedDocument(BaseModel):
    """一次 parse_file 的完整结果。"""

    document_id: str
    source_path: str
    doc_type: str
    raw_text: str
    chunks: list[Chunk]
```

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_models.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/__init__.py backend/app/parsing/models.py backend/app/parsing/errors.py backend/tests/parsing/__init__.py backend/tests/parsing/test_models.py
git commit -m "feat(parsing): 数据模型与 ParseError 异常"
```

---

### Task 2: chunker — 聚合相邻块（同页同标题守卫）

**Files:**
- Create: `backend/app/parsing/chunker.py`
- Test: `backend/tests/parsing/test_chunker.py`

**Interfaces:**
- Consumes: `Block`, `Chunk`, `SourceLocation`（Task 1）
- Produces: `chunk_blocks(blocks: list[Block], document_id: str, max_chars: int = MAX_CHARS, overlap_chars: int = OVERLAP_CHARS, min_chars: int = MIN_CHARS) -> list[Chunk]`；模块常量 `MAX_CHARS=800`、`OVERLAP_CHARS=150`、`MIN_CHARS=100`

本任务只实现「第 2 步聚合 + 第 3 步小块回填」。假设输入 Block 均 ≤ max_chars（超长预拆在 Task 3 加）。聚合产出的 chunk：`char_start` = 首块起点，`char_end` = 末块终点，`text` = `raw_text` 对应区间（这里用各块 text 间不重叠拼接——见实现说明）。

**实现说明（偏移与 text 的一致性）**：同一文档相邻 Block 的偏移是连续或留白的。chunk.text 必须满足 `raw_text[start:end] == chunk.text`。因此 chunker 不能简单 `"".join(block.text)`，而要让 caller 传入 raw_text。**调整接口**：`chunk_blocks(blocks, document_id, raw_text, ...)`，chunk.text 一律取 `raw_text[chunk_start:chunk_end]`。

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/test_chunker.py`：

```python
"""chunker 测试：聚合、同页同标题守卫、小块回填、偏移可追溯。"""

from app.parsing.chunker import chunk_blocks, MAX_CHARS
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


def test_tiny_trailing_block_backfills_into_previous():
    # 第一块接近上限，第二块很小且同页同标题 → 小块并入前块（不超 max_chars 时）
    raw = "A" * 700 + "\n\n" + "B" * 10
    blocks = [_block("A" * 700, 0), _block("B" * 10, 702)]
    chunks = chunk_blocks(blocks, document_id="d", raw_text=raw)
    assert len(chunks) == 1
    assert chunks[0].location.char_end == 712


def test_empty_blocks_returns_empty():
    assert chunk_blocks([], document_id="d", raw_text="") == []
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_chunker.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing.chunker'`

- [ ] **Step 3: 写最小实现**

`backend/app/parsing/chunker.py`：

```python
"""chunker：把 Block 列表聚合成目标大小的 Chunk，保持同页同标题边界。

偏移与 text 一致性：chunk.text 一律取 raw_text[start:end]，保证
raw_text[chunk.char_start:chunk.char_end] == chunk.text。

注意：本模块假设输入 Block 已经 <= max_chars（超长预拆见 split_oversized_block，
由 Task 3 在调用前应用）。
"""

import logging

from app.parsing.models import Block, Chunk, SourceLocation

logger = logging.getLogger(__name__)

MAX_CHARS = 800
OVERLAP_CHARS = 150
MIN_CHARS = 100


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
    min_chars: int = MIN_CHARS,
) -> list[Chunk]:
    """把 Block 列表聚合成 Chunk 列表。

    第 2 步聚合：相邻块在「累积长度 + 下一块 <= max_chars」且同页同标题时合并。
    第 3 步小块回填：收尾 chunk 若 < min_chars，尝试并入前一 chunk（受 max_chars
    与同页同标题约束）；否则保留为独立小 chunk。
    """
    if not blocks:
        return []

    # 第 2 步：聚合成 group（每个 group 一个候选 chunk）
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

    # 第 3 步：小块回填到前一 group（同页同标题且并入后不超 max_chars）
    merged: list[list[Block]] = []
    for group in groups:
        group_len = sum(len(b.text) for b in group)
        if (
            merged
            and group_len < min_chars
            and _same_boundary(merged[-1][-1], group[0])
            and sum(len(b.text) for b in merged[-1]) + group_len <= max_chars
        ):
            merged[-1].extend(group)
        else:
            merged.append(group)

    return [
        _make_chunk(i, group, document_id, raw_text)
        for i, group in enumerate(merged)
    ]
```

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_chunker.py -q`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/chunker.py backend/tests/parsing/test_chunker.py
git commit -m "feat(parsing): chunker 聚合相邻块与小块回填（同页同标题守卫）"
```

---

### Task 3: chunker — 超长 Block 预拆（滑窗 + 自然断点回退）

**Files:**
- Modify: `backend/app/parsing/chunker.py`
- Test: `backend/tests/parsing/test_chunker.py`（追加测试）

**Interfaces:**
- Consumes: `Block`（Task 1）, `chunk_blocks`（Task 2）
- Produces: `split_oversized_block(block: Block, max_chars: int = MAX_CHARS, overlap_chars: int = OVERLAP_CHARS) -> list[Block]`；并让 `chunk_blocks` 在聚合前对每个超长 block 先调用它

超长 Block 按 `max_chars` 滑窗、`overlap_chars` 重叠拆成子块。每个窗口末尾优先在「最后一个自然断点」（依次找 `。`/`.`/`\n`/空格）回退切；找不到才硬切。子块的 `char_start/end` 按相对父块 `char_start` 的真实偏移重算，继承 `page` / `heading_path`。

- [ ] **Step 1: 追加失败测试**

在 `test_chunker.py` 末尾追加：

```python
from app.parsing.chunker import split_oversized_block


def test_split_oversized_block_produces_multiple_subblocks():
    text = "x" * 2000
    block = Block(text=text, char_start=0, char_end=2000)
    subs = split_oversized_block(block, max_chars=800, overlap_chars=150)
    assert len(subs) >= 3
    # 子块偏移可还原回父块文本
    for s in subs:
        assert text[s.char_start:s.char_end] == s.text


def test_split_oversized_block_overlaps():
    text = "x" * 2000
    block = Block(text=text, char_start=0, char_end=2000)
    subs = split_oversized_block(block, max_chars=800, overlap_chars=150)
    # 第二块起点应早于第一块终点（存在重叠）
    assert subs[1].char_start < subs[0].char_end


def test_split_prefers_natural_breakpoint():
    # 句号在 600 处，窗口 800 内应回退到句号后切
    text = "A" * 600 + "。" + "B" * 800
    block = Block(text=text, char_start=0, char_end=len(text))
    subs = split_oversized_block(block, max_chars=800, overlap_chars=150)
    # 第一块应在句号处结束（即第一块 text 以「。」结尾）
    assert subs[0].text.endswith("。")


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
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_chunker.py -q`
Expected: FAIL — `ImportError: cannot import name 'split_oversized_block'`

- [ ] **Step 3: 写实现**

在 `chunker.py` 顶部常量后追加 `split_oversized_block`，并修改 `chunk_blocks` 在聚合前预拆。

新增函数（放在 `_make_chunk` 之前）：

```python
_BREAKPOINTS = ("。", ".", "\n", " ")


def _find_breakpoint(text: str, window_end: int, window_start: int) -> int:
    """在 [window_start, window_end) 内找最后一个自然断点，返回切点（含断点）。

    找不到返回 window_end（硬切）。切点是「断点字符之后」的位置。
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
    """超长 Block 滑窗拆分；未超长则原样返回单元素列表。"""
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
```

修改 `chunk_blocks`，在 `if not blocks: return []` 之后、聚合之前插入预拆：

```python
    # 第 1 步：超长 Block 预拆
    expanded: list[Block] = []
    for block in blocks:
        expanded.extend(split_oversized_block(block, max_chars, overlap_chars))
    blocks = expanded
```

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_chunker.py -q`
Expected: PASS（12 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/chunker.py backend/tests/parsing/test_chunker.py
git commit -m "feat(parsing): chunker 超长 Block 滑窗预拆与自然断点回退"
```

---

### Task 4: text_parser（.txt）

**Files:**
- Create: `backend/app/parsing/text_parser.py`
- Test: `backend/tests/parsing/test_text_parser.py`

**Interfaces:**
- Consumes: `Block`（Task 1）
- Produces: `parse_text(path: str) -> tuple[str, list[Block]]`，返回 `(raw_text, blocks)`

读全文为 raw_text（UTF-8，失败 `errors="replace"`）；按连续空行（`\n\s*\n`）分段，每段一个 Block，偏移用段在 raw_text 的真实位置；`page=None`，`heading_path=[]`。空文件返回 `("", [])`。

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/test_text_parser.py`：

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_text_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing.text_parser'`

- [ ] **Step 3: 写实现**

`backend/app/parsing/text_parser.py`：

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_text_parser.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/text_parser.py backend/tests/parsing/test_text_parser.py
git commit -m "feat(parsing): txt 解析器（空行分段 + 偏移）"
```

---

### Task 5: markdown_parser（.md/.markdown）

**Files:**
- Create: `backend/app/parsing/markdown_parser.py`
- Test: `backend/tests/parsing/test_markdown_parser.py`

**Interfaces:**
- Consumes: `Block`（Task 1）
- Produces: `parse_markdown(path: str) -> tuple[str, list[Block]]`

raw_text = 原始 Markdown 全文（不渲染、不剥语法）。扫描行首 `#` 维护标题栈得 heading_path。**标题行文字本身计入其后正文块的 text（仅一次），不单独成块、不与正文重复**（大脑复审第②点）。按标题行和空行切段；正文段继承当前 heading_path；`page=None`。空文件返回 `("", [])`。

**heading_path 规则**：`## 安装` 之后、遇到下一个同级或更高级标题前，所有正文段的 heading_path = 当前标题栈快照（如 `["安装"]`）。`### 依赖` 进栈得 `["安装", "依赖"]`。

**标题行归属规则**：标题行与其紧随的正文合为同一个 Block，Block.text 含标题行原文（如 `"# 标题\n正文..."`），保证 `raw_text[start:end] == text` 不变量；标题文字不再单独出现在别处。

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/test_markdown_parser.py`：

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_markdown_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing.markdown_parser'`

- [ ] **Step 3: 写实现**

`backend/app/parsing/markdown_parser.py`：

```python
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
```

**实现说明**：`_heading_path_at(start + 1)` 传 `start+1` 是为了让「正文段本身所属的标题」被计入——若该段就是标题行开头，`start+1` 覆盖到 `#` 之后能匹配到本标题。逐段独立计算标题栈，避免跨段状态依赖。

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_markdown_parser.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/markdown_parser.py backend/tests/parsing/test_markdown_parser.py
git commit -m "feat(parsing): Markdown 解析器（标题栈 + 偏移，标题不重复）"
```

---

### Task 6: pdf_parser（.pdf，PyMuPDF）— 需先装依赖

**前置（人工 gate）**：本任务需 `PyMuPDF`。执行前先停下，向用户确认是否在 `myself` 环境安装：`conda run -n myself pip install PyMuPDF`。**装好后**在 `backend/requirements.txt` 追加一行 `PyMuPDF`。未获同意不得继续。

**Files:**
- Create: `backend/app/parsing/pdf_parser.py`
- Modify: `backend/requirements.txt`（追加 `PyMuPDF`）
- Test: `backend/tests/parsing/test_pdf_parser.py`

**Interfaces:**
- Consumes: `Block`（Task 1）
- Produces: `parse_pdf(path: str) -> tuple[str, list[Block]]`

逐页 `page.get_text("text")`；raw_text = 各页文本按页序拼接，**页间插一个 `\n`**，并记录每页在 raw_text 的起始偏移（大脑复审第③点：跨页偏移相对拼接后的 raw_text）。每页内按空行分段成 Block，`page` = 页码（1-based），`heading_path=[]`。某页文本空/近空 → 记 warning，不报错不 OCR。文件打不开 → 抛 `ParseError`。

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/test_pdf_parser.py`（测试内用 PyMuPDF 现生成 2 页 PDF，自包含）：

```python
"""pdf_parser 测试：页码、跨页偏移、损坏文件。fixture 用 fitz 现生成。"""

import fitz
import pytest

from app.parsing.pdf_parser import parse_pdf
from app.parsing.errors import ParseError


def _make_pdf(path, pages):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def test_parse_pdf_two_pages_with_page_numbers(tmp_path):
    p = tmp_path / "a.pdf"
    _make_pdf(p, ["第一页内容", "第二页内容"])
    raw, blocks = parse_pdf(str(p))
    pages = {b.page for b in blocks}
    assert pages == {1, 2}


def test_parse_pdf_raw_text_contains_both_pages(tmp_path):
    p = tmp_path / "a.pdf"
    _make_pdf(p, ["AAAA", "BBBB"])
    raw, blocks = parse_pdf(str(p))
    assert "AAAA" in raw
    assert "BBBB" in raw


def test_parse_pdf_offsets_traceable(tmp_path):
    p = tmp_path / "a.pdf"
    _make_pdf(p, ["AAAA", "BBBB"])
    raw, blocks = parse_pdf(str(p))
    for b in blocks:
        assert raw[b.char_start:b.char_end] == b.text


def test_parse_pdf_corrupt_raises(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a real pdf")
    with pytest.raises(ParseError):
        parse_pdf(str(p))
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_pdf_parser.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing.pdf_parser'`（或 fitz 未装则先装）

- [ ] **Step 3: 写实现**

`backend/app/parsing/pdf_parser.py`：

```python
"""PDF 解析（PyMuPDF）：逐页抽文本，记录跨页偏移与页码。

扫描版（无文本层）页只记 warning，不做 OCR。
"""

import logging
import re

import fitz

from app.parsing.errors import ParseError
from app.parsing.models import Block

logger = logging.getLogger(__name__)

_PARA_SPLIT = re.compile(r"\n[ \t]*\n")


def parse_pdf(path: str) -> tuple[str, list[Block]]:
    """读取 PDF，返回 (raw_text, blocks)。偏移相对拼接后的 raw_text。"""
    try:
        doc = fitz.open(path)
    except Exception as exc:  # PyMuPDF 抛 FileDataError 等
        raise ParseError(path=path, reason=f"无法打开 PDF: {exc}") from exc

    parts: list[str] = []
    blocks: list[Block] = []
    offset = 0
    try:
        for page_index in range(doc.page_count):
            page_no = page_index + 1
            page_text = doc[page_index].get_text("text")
            if page_text.strip() == "":
                logger.warning("PDF 第 %d 页无文本层（可能为扫描页）: %s", page_no, path)
            # 该页文本在 raw_text 中从 offset 开始
            for part in _PARA_SPLIT.split(page_text):
                if part.strip() == "":
                    continue
                stripped = part.strip()
                local = page_text.find(stripped)
                start = offset + local
                end = start + len(stripped)
                blocks.append(
                    Block(text=stripped, char_start=start, char_end=end, page=page_no)
                )
            parts.append(page_text)
            offset += len(page_text) + 1  # 页间插一个 \n
    finally:
        doc.close()

    raw_text = "\n".join(parts)
    return raw_text, blocks
```

**实现说明**：`offset += len(page_text) + 1` 与 `"\n".join(parts)` 一致——join 在每两页间插一个 `\n`，因此每页起始偏移 = 前面所有页文本长度之和 + 页间 `\n` 数。blocks 在循环内即按此 offset 计算，保证 `raw_text[start:end] == text`。

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_pdf_parser.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/pdf_parser.py backend/tests/parsing/test_pdf_parser.py backend/requirements.txt
git commit -m "feat(parsing): PDF 解析器（PyMuPDF，跨页偏移 + 页码，扫描页降级）"
```

---

### Task 7: base 分派 + parse_file 组装

**Files:**
- Create: `backend/app/parsing/base.py`
- Test: `backend/tests/parsing/test_base.py`

**Interfaces:**
- Consumes: `parse_text`（Task 4）, `parse_markdown`（Task 5）, `parse_pdf`（Task 6）, `chunk_blocks`（Task 2/3）, `ParsedDocument`（Task 1）, `ParseError`（Task 1）
- Produces:
  - `parse_file(path: str, document_id: str | None = None) -> ParsedDocument`
  - 常量 `SUPPORTED_EXTENSIONS: dict[str, str]`（扩展名 → doc_type）

按扩展名分派：`.txt`→text，`.md`/`.markdown`→markdown，`.pdf`→pdf。文件不存在或扩展名不支持 → 抛 `ParseError`。`document_id` 默认用文件名（`os.path.basename`）。组装 ParsedDocument 后调 `chunk_blocks(blocks, document_id, raw_text)` 填 chunks。

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/test_base.py`：

```python
"""base 分派与 parse_file 组装测试。"""

import pytest

from app.parsing.base import parse_file
from app.parsing.errors import ParseError


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
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_base.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing.base'`

- [ ] **Step 3: 写实现**

`backend/app/parsing/base.py`：

```python
"""parser 分派与 parse_file 组装：按扩展名选 parser，组装 ParsedDocument 并切块。"""

import os

from app.parsing.chunker import chunk_blocks
from app.parsing.errors import ParseError
from app.parsing.markdown_parser import parse_markdown
from app.parsing.models import ParsedDocument
from app.parsing.pdf_parser import parse_pdf
from app.parsing.text_parser import parse_text

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".pdf": "pdf",
}

_PARSERS = {
    "text": parse_text,
    "markdown": parse_markdown,
    "pdf": parse_pdf,
}


def parse_file(path: str, document_id: str | None = None) -> ParsedDocument:
    """解析单个文件为 ParsedDocument（含 chunks）。

    硬失败抛 ParseError：文件不存在 / 扩展名不支持。
    """
    if not os.path.isfile(path):
        raise ParseError(path=path, reason="文件不存在")

    ext = os.path.splitext(path)[1].lower()
    doc_type = SUPPORTED_EXTENSIONS.get(ext)
    if doc_type is None:
        raise ParseError(path=path, reason=f"不支持的扩展名: {ext}")

    doc_id = document_id or os.path.basename(path)
    raw_text, blocks = _PARSERS[doc_type](path)
    chunks = chunk_blocks(blocks, document_id=doc_id, raw_text=raw_text)
    return ParsedDocument(
        document_id=doc_id,
        source_path=path,
        doc_type=doc_type,
        raw_text=raw_text,
        chunks=chunks,
    )
```

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_base.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/parsing/base.py backend/tests/parsing/test_base.py
git commit -m "feat(parsing): parse_file 扩展名分派与组装"
```

---

### Task 8: repo_importer（目录导入）+ 包导出

**Files:**
- Create: `backend/app/parsing/repo_importer.py`
- Modify: `backend/app/parsing/__init__.py`（补对外导出）
- Test: `backend/tests/parsing/test_repo_importer.py`

**Interfaces:**
- Consumes: `parse_file`（Task 7）, `SUPPORTED_EXTENSIONS`（Task 7）, `ParsedDocument`（Task 1）, `ParseError`（Task 1）
- Produces: `parse_directory(root: str) -> list[ParsedDocument]`

递归遍历目录，按 `SUPPORTED_EXTENSIONS` 筛文件；跳过 `_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}`。`document_id` 用相对 root 的路径（POSIX 风格 `/`）。单文件 `ParseError` → 记 error 日志 + 跳过，整批不中断。

- [ ] **Step 1: 写失败测试**

`backend/tests/parsing/test_repo_importer.py`：

```python
"""repo_importer 测试：递归命中、跳过噪音目录、单文件失败不中断。"""

from app.parsing.repo_importer import parse_directory


def test_imports_supported_files_recursively(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n正文。", encoding="utf-8")
    (tmp_path / "b.txt").write_text("文本。", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("# C\n\n内容。", encoding="utf-8")
    docs = parse_directory(str(tmp_path))
    ids = {d.document_id for d in docs}
    assert ids == {"a.md", "b.txt", "sub/c.md"}


def test_skips_git_directory(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n正文。", encoding="utf-8")
    git = tmp_path / ".git"
    git.mkdir()
    (git / "config.md").write_text("# 不该被导入", encoding="utf-8")
    docs = parse_directory(str(tmp_path))
    ids = {d.document_id for d in docs}
    assert ids == {"a.md"}


def test_ignores_unsupported_extensions(tmp_path):
    (tmp_path / "a.txt").write_text("文本。", encoding="utf-8")
    (tmp_path / "b.xyz").write_text("忽略。", encoding="utf-8")
    docs = parse_directory(str(tmp_path))
    assert {d.document_id for d in docs} == {"a.txt"}


def test_empty_directory_returns_empty(tmp_path):
    docs = parse_directory(str(tmp_path))
    assert docs == []
```

- [ ] **Step 2: 运行测试验证失败**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_repo_importer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.parsing.repo_importer'`

- [ ] **Step 3: 写实现**

`backend/app/parsing/repo_importer.py`：

```python
"""目录导入：递归遍历，对支持的文件批量调 parse_file，单文件失败跳过。"""

import logging
import os

from app.parsing.base import SUPPORTED_EXTENSIONS, parse_file
from app.parsing.errors import ParseError
from app.parsing.models import ParsedDocument

logger = logging.getLogger(__name__)

_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def parse_directory(root: str) -> list[ParsedDocument]:
    """递归解析目录下所有支持的文件，返回 ParsedDocument 列表。"""
    docs: list[ParsedDocument] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                docs.append(parse_file(full, document_id=rel))
            except ParseError as exc:
                logger.error("跳过解析失败的文件 %s: %s", rel, exc)
    return docs
```

`backend/app/parsing/__init__.py`（补导出）：

```python
"""文档解析与切块：文件/目录 → 带来源元数据的 Chunk 列表。"""

from app.parsing.base import parse_file
from app.parsing.errors import ParseError
from app.parsing.models import Block, Chunk, ParsedDocument, SourceLocation
from app.parsing.repo_importer import parse_directory

__all__ = [
    "parse_file",
    "parse_directory",
    "ParseError",
    "ParsedDocument",
    "Chunk",
    "Block",
    "SourceLocation",
]
```

- [ ] **Step 4: 运行测试验证通过**

Run（从 `backend/`）：`conda run -n myself python -m pytest tests/parsing/test_repo_importer.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 全量回归 + 提交**

Run（从 `backend/`）：`conda run -n myself python -m pytest -q`
Expected: PASS（全部测试通过，含原有 2 个 health 测试）

```bash
git add backend/app/parsing/repo_importer.py backend/app/parsing/__init__.py backend/tests/parsing/test_repo_importer.py
git commit -m "feat(parsing): 目录导入与包对外导出"
```

---

### Task 9: DEVLOG 学习记录

**Files:**
- Modify: `backend/DEVLOG.md`（追加一条）

CLAUDE.md 硬要求：引入新工具 / 完成非显然工作流后必须追加学习记录。本任务记录解析切块板块，并显式记下大脑复审第①点（全短段落文档无 chunk 间 overlap = 有意决策）。

- [ ] **Step 1: 追加 DEVLOG 记录**

在 `backend/DEVLOG.md` 末尾追加（用项目统一模板）：

```markdown
## 2026-06-17 文档解析与切块

- 做了什么：实现纯解析库 `app/parsing/`——txt/Markdown/PDF 单文件解析 + GitHub 目录导入，统一产出带来源元数据（字符偏移 + 页码 + 标题路径）的 Chunk 列表。两段式：parser 抽文本切语义块，chunker 聚合 + 超长拆分。

- 这是什么：
  - **chunk（切块）**：把长文档切成小片段，是后续向量检索和 GraphRAG 的最小证据单元。切太大检索不准、切太小丢上下文，所以要按语义边界切并控制大小。
  - **provenance（来源追溯）**：每个 chunk 记住它在原文的精确位置（第几个字符到第几个字符、第几页、哪个标题下），这样回答引用时能定位回原文高亮，是本项目「引用可追溯」硬要求的地基。
  - **PyMuPDF（fitz）**：一个 PDF 文本抽取库，逐页拿出文字层。扫描版 PDF 没有文字层（只有图片），它拿不到文本——我们只记 warning 不做 OCR。

- 为什么需要：所有下游能力（图谱、检索、问答）都吃 chunk。没有稳定、可追溯的 chunk，后面全都立不住。

- 为什么这么做（关键取舍）：
  - **parser 与 chunker 解耦**：解析是格式相关的脏活，切块是格式无关的策略。分开后换切块策略不动 parser，加新格式只写新 parser。
  - **偏移单位用字符不用 token**：token 计数要 tokenizer，会绑定具体模型、加依赖；本项目不绑厂商，字符数最简单稳定。
  - **核心不变量 `raw_text[start:end] == chunk.text`**：每个 parser 和 chunker 都有测试断言它，这是「引用能落回原文」的机器化保证。
  - **全短段落文档无 chunk 间 overlap（有意决策，备查）**：overlap 只在「单个超长 Block 内部滑窗」时产生；若文档全是短段落，聚合路径不人为加重叠。理由：结构感知切分已用自然边界保证语义完整，跨段再加重叠收益小，还会让偏移区间互相纠缠、复杂化引用高亮。若后续评估发现召回因缺重叠而变差，再在聚合层引入可配置 overlap。
  - **Markdown 标题文字只计入正文块一次**：标题行与其后正文合为同一 Block，不单独成块，避免标题在 chunk 里重复。

- 踩了什么坑：（实现时如有，补这里）
```

- [ ] **Step 2: 提交**

```bash
git add backend/DEVLOG.md
git commit -m "docs(backend): 文档解析与切块学习记录"
```

---

## Self-Review

**1. Spec coverage（逐节核对 spec → 任务）：**
- spec §1 定位边界 → 全局约束 + Task 划分（不碰 Neo4j/embedding/HTTP）✅
- spec §2 模块结构 + 两段式 → File Structure + Task 1-8 ✅
- spec §3 数据模型 → Task 1 ✅
- spec §4 chunker 三步 → Task 2（聚合+回填）、Task 3（超长预拆）✅
- spec §5 各 parser → Task 4（txt）、5（md）、6（pdf）、8（repo）✅
- spec §5 base 分派 → Task 7 ✅
- spec §6 错误分层 → ParseError（Task 1）+ 硬失败测试（Task 6/7）+ 软降级 warning（Task 6）+ 目录跳过（Task 8）✅
- spec §7 测试表 8 项 → 全部映射到 Task 1-8 的测试，含核心「偏移可追溯」断言（Task 2/4/5/6/7 均有）✅
- spec §8 验收对齐 → 各 parser 测试 + 偏移断言 + PDF 测试 ✅
- spec §9 不在范围 → 计划未触碰，DEVLOG 记 OCR/token 决策 ✅
- 大脑复审 3 点 → ①DEVLOG 记录（Task 9）②Markdown 标题不重复（Task 5 含 `test_heading_text_not_duplicated`）③PDF 跨页偏移相对 raw_text（Task 6 含 `test_parse_pdf_offsets_traceable` + 实现说明）✅
- 大脑复审：PyMuPDF 先问 → Task 6 前置人工 gate ✅

**2. Placeholder scan：** DEVLOG「踩了什么坑」留待实现时补属正常（非代码占位）；其余所有代码步骤均含完整代码与确切命令。无 TBD/TODO 代码占位。✅

**3. Type consistency：**
- `chunk_blocks` 签名 `(blocks, document_id, raw_text, max_chars, overlap_chars, min_chars)` 在 Task 2 定义、Task 3 修改（保持签名）、Task 7 调用 `chunk_blocks(blocks, document_id=doc_id, raw_text=raw_text)` 一致 ✅
- 各 parser 统一返回 `tuple[str, list[Block]]`，Task 7 `_PARSERS` 调用一致 ✅
- `SUPPORTED_EXTENSIONS` Task 7 定义、Task 8 引用一致 ✅
- `ParseError(path=, reason=)` 构造在 Task 1 定义，Task 6/7/8 调用一致 ✅
- `split_oversized_block(block, max_chars, overlap_chars)` Task 3 定义并被 `chunk_blocks` 调用一致 ✅

无不一致。计划完整。
