# Knowledge Graph Evaluation Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立能区分“召回成功”和“图谱可信”的评估基线，为后续解析、抽取、消歧和前端升级提供可回归的质量门槛。

**Architecture:** 评估层不改变现有入库链路。新增纯函数指标模块和小型人工标注夹具，输入可以是抽取候选/最终 accepted 图谱，输出 pooled、macro、precision、噪声率、关系语义正确率和 provenance 覆盖率。所有指标均能脱离 LLM/Neo4j 单测运行。

**Tech Stack:** Python 3.11+ / pytest / Pydantic / JSONL fixtures。

## Global Constraints

- 只修改 `evals/`、必要的 `docs/evaluation.md` 和 `evals/DEVLOG.md`；不修改业务抽取代码。
- 不调用真实 LLM、不写 Neo4j、不重写历史 `evals/report.md`。
- 现有 pooled/macro 召回接口必须保持兼容。
- 所有新指标必须有至少一个正例、一个负例和一个空输入测试。

### Task 1: Define labeled candidate fixtures

**Files:**
- Create: `evals/quality_fixtures.jsonl`
- Test: `evals/tests/test_quality_fixtures.py`

**Interfaces:**
- Each JSONL row contains `sample_id`, `text_kind`, `gold_entities`, `gold_relations`, `candidate_entities`, `candidate_relations`.
- Entity fields: `name`, `type`, `accepted`, `evidence_present`.
- Relation fields: `source`, `type`, `target`, `accepted`, `semantically_correct`.

- [ ] **Step 1: Write the failing fixture loader test**

```python
def test_quality_fixture_has_gold_and_negative_candidates():
    rows = load_quality_fixtures()
    assert rows
    assert any(not item.accepted for item in rows[0].candidate_entities)
    assert any(not item.semantically_correct for item in rows[0].candidate_relations)
```

- [ ] **Step 2: Run the test and verify it fails because the loader is absent**

Run: `D:\Anaconda\envs\myself\python.exe -m pytest evals/tests/test_quality_fixtures.py -q`

Expected: collection failure for missing `load_quality_fixtures`.

- [ ] **Step 3: Implement the smallest typed loader**

Create `evals/quality_fixtures.py` with Pydantic models and:

```python
def load_quality_fixtures(path: Path | None = None) -> list[QualityFixture]:
    source = path or Path(__file__).with_name("quality_fixtures.jsonl")
    return [QualityFixture.model_validate_json(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
```

- [ ] **Step 4: Run the focused test and verify it passes**

Expected: fixture loader test passes and no real service is contacted.

- [ ] **Step 5: Commit**

```bash
git add evals/quality_fixtures.py evals/quality_fixtures.jsonl evals/tests/test_quality_fixtures.py
git commit -m "test(evals): add graph quality fixtures"
```

### Task 2: Add deterministic quality metrics

**Files:**
- Create: `evals/quality_metrics.py`
- Create: `evals/tests/test_quality_metrics.py`
- Modify: `docs/evaluation.md`

**Interfaces:**

```python
def summarize_entity_precision(hit_counts: list[int], accepted_counts: list[int]) -> tuple[float, float]: ...
def summarize_relation_correctness(correct_counts: list[int], accepted_counts: list[int]) -> tuple[float, float]: ...
def summarize_noise_rate(noise_counts: list[int], candidate_counts: list[int]) -> tuple[float, float]: ...
def provenance_coverage(accepted_items: list[dict]) -> float: ...
```

Each pair returns `(pooled, macro)`; mismatched lengths raise `ValueError`; empty input returns `(0.0, 0.0)`.

- [ ] **Step 1: Write failing tests** for pooled/macro precision, relation correctness, noise rate, empty input, mismatched lists, and missing provenance.
- [ ] **Step 2: Run:** `D:\Anaconda\envs\myself\python.exe -m pytest evals/tests/test_quality_metrics.py -q` and verify the new imports/functions fail.
- [ ] **Step 3: Implement the pure functions** with no file, LLM, or Neo4j access.
- [ ] **Step 4: Re-run focused tests, then all eval tests:** `D:\Anaconda\envs\myself\python.exe -m pytest evals/tests -q`.
- [ ] **Step 5: Document definitions** in `docs/evaluation.md`: precision is accepted-and-gold / accepted; relation correctness is semantically correct / accepted; endpoint resolution remains auxiliary.
- [ ] **Step 6: Commit** with `git add evals/quality_metrics.py evals/tests/test_quality_metrics.py docs/evaluation.md && git commit -m "feat(evals): measure graph precision and provenance"`.

### Task 3: Add code/noise and resolution fixtures

**Files:**
- Modify: `evals/quality_fixtures.jsonl`
- Modify: `evals/tests/test_quality_fixtures.py`
- Modify: `evals/DEVLOG.md`

- [ ] **Step 1: Add labeled cases** for fenced Python, JSON config, shell paths, logs, generic nouns, aliases (`Neo4j`/`Neo4j database`), bilingual names, and a valid technical prose paragraph.
- [ ] **Step 2: Add tests** asserting the fixture contains one expected skip case and one expected merge case.
- [ ] **Step 3: Run:** `D:\Anaconda\envs\myself\python.exe -m pytest evals/tests -q`.
- [ ] **Step 4: Add a DEVLOG entry** explaining why precision/noise metrics are required in addition to recall.
- [ ] **Step 5: Commit** with `git commit -am "test(evals): cover code noise and aliases"`.

### Task 4: Final worktree verification

- [ ] Run `D:\Anaconda\envs\myself\python.exe -m pytest evals/tests -q` and `D:\Anaconda\envs\myself\python.exe -m py_compile evals/quality_fixtures.py evals/quality_metrics.py`.
- [ ] Run `git diff --check` and confirm `git status --short` is empty.
- [ ] Report changed files, test count, and interfaces consumed by `feat/kg-parsing`.

