# Knowledge Graph Content-Aware Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏字符偏移和现有解析验收的前提下，把 Markdown/文本块标记为正文、代码、配置、表格、列表或日志，并为后续抽取提供明确策略。

**Architecture:** 解析层只负责结构识别和元数据，不调用 LLM、不决定最终实体。`Block` 保持原始文本和偏移，新增 `content_kind`、`language`、`extraction_policy`；`Chunk` 聚合时只能合并兼容内容类型和标题边界。普通抽取策略由 metadata 驱动，真正的 Schema/candidate 逻辑留给后续 extraction worktree。

**Tech Stack:** Python 3.11+ / Pydantic / pytest / Markdown 原文扫描。

## Global Constraints

- Work only in `D:\AgenX\archigraph-kg-parsing` on branch `feat/kg-parsing`.
- Base must be the main commit that already contains `feat/kg-evaluation`.
- Do not modify extraction, Neo4j writer, API, frontend, or `tasks/todo.md`.
- Preserve `raw_text[char_start:char_end] == block/chunk.text` for every existing and new fixture.
- Do not add a Markdown rendering dependency unless the worker documents the limitation and receives approval; prefer the existing parser boundary.
- Use TDD and update `backend/DEVLOG.md` or `docs/DEVLOG.md` only for non-obvious parsing decisions.

### Task 1: Add content-kind metadata

**Files:**
- Modify: `backend/app/parsing/models.py`
- Test: `backend/tests/parsing/test_models.py`

**Interfaces:**

```python
class ContentKind(str, Enum):
    PROSE = "prose"
    CODE = "code"
    CONFIG = "config"
    TABLE = "table"
    LIST = "list"
    LOG = "log"
    HEADING = "heading"

class ExtractionPolicy(str, Enum):
    NORMAL = "normal"
    SKIP = "skip"
    SPECIALIZED = "specialized"
```

`Block` and `Chunk` expose `content_kind`, `language: str | None`, and `extraction_policy`, defaulting to `PROSE`, `None`, and `NORMAL` so old callers remain valid.

- [ ] Write tests for defaults, explicit code metadata, and Pydantic serialization.
- [ ] Run `D:\Anaconda\envs\myself\python.exe -m pytest backend/tests/parsing/test_models.py -q` and observe RED.
- [ ] Implement the enums and fields with no parser behavior changes.
- [ ] Re-run the focused test and then `D:\Anaconda\envs\myself\python.exe -m pytest backend/tests/parsing -q`.
- [ ] Commit `feat(parsing): add content kind metadata`.

### Task 2: Classify Markdown structures

**Files:**
- Create: `backend/app/parsing/content_classifier.py`
- Modify: `backend/app/parsing/markdown_parser.py`
- Test: `backend/tests/parsing/test_markdown_parser.py`
- Test: `backend/tests/parsing/test_content_classifier.py`

**Interfaces:**

```python
def classify_block(text: str, *, fenced_language: str | None = None) -> tuple[ContentKind, str | None, ExtractionPolicy]: ...
```

Required deterministic rules: fenced regions with a language are `CODE` and `SPECIALIZED`; JSON/YAML/TOML-like fenced regions are `CONFIG` and `SKIP`; Markdown tables are `TABLE` and `NORMAL`; list-only blocks are `LIST` and `NORMAL`; obvious timestamped log lines are `LOG` and `SKIP`; ordinary paragraphs are `PROSE` and `NORMAL`.

- [ ] Add RED tests for a Python fence, JSON fence, Markdown table, bullet list, timestamped log, and ordinary paragraph.
- [ ] Run both focused test files and verify the classifier import/behavior fails.
- [ ] Implement only deterministic classification and keep unknown fences safe as `CODE/SPECIALIZED`.
- [ ] Update Markdown parsing to preserve the full fenced block and its original offsets; headings remain context, not entities.
- [ ] Run `D:\Anaconda\envs\myself\python.exe -m pytest backend/tests/parsing/test_content_classifier.py backend/tests/parsing/test_markdown_parser.py -q`.
- [ ] Commit `feat(parsing): classify markdown content blocks`.

### Task 3: Propagate metadata through chunking

**Files:**
- Modify: `backend/app/parsing/chunker.py`
- Test: `backend/tests/parsing/test_chunker.py`
- Test: `backend/tests/parsing/test_base.py`

- [ ] Add RED tests proving code/config blocks keep their metadata and are not merged into adjacent prose blocks.
- [ ] Run the focused tests and observe the current chunker loses the required metadata/boundary.
- [ ] Make `_same_boundary` require compatible `content_kind`, `language`, and `extraction_policy`; copy metadata into `Chunk`.
- [ ] Keep overlap splitting offset-safe and test `raw_text[start:end] == text` for mixed blocks.
- [ ] Run all parsing tests and the existing backend baseline.
- [ ] Commit `feat(parsing): preserve content policy through chunks`.

### Task 4: Expose parser policy without changing extraction

**Files:**
- Modify: `backend/app/parsing/__init__.py`
- Modify: `backend/app/parsing/base.py`
- Test: `backend/tests/parsing/test_base.py`
- Modify: `backend/DEVLOG.md` or `docs/DEVLOG.md`

- [ ] Add a test that `parse_file` returns policy metadata for a mixed Markdown fixture and keeps all source offsets valid.
- [ ] Run the focused test and verify the public parser result lacks the new metadata.
- [ ] Export the new enums and preserve the existing `ParsedDocument` API; do not filter chunks in this task.
- [ ] Add a five-field DEVLOG entry explaining why parser policy is metadata rather than an extraction-side hard-coded filename check.
- [ ] Run `D:\Anaconda\envs\myself\python.exe -m pytest backend/tests/parsing -q` and `D:\Anaconda\envs\myself\python.exe -m py_compile backend/app/parsing/*.py`.
- [ ] Commit `docs(parsing): record content-aware parsing contract`.

### Task 5: Final worktree verification

- [ ] Run the parsing test suite and the relevant backend full suite.
- [ ] Run `git diff --check` and confirm `git status --short` is empty.
- [ ] Report the exact metadata fields and classification rules consumed by `feat/kg-extraction`.
