# Evaluation Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hallucination sentence splitting Markdown-aware and expose both pooled and macro entity-recall metrics without running paid evaluation calls.

**Architecture:** Move deterministic metric helpers into `evals/metrics.py`, cover them with pure pytest tests, and keep `run_eval.py` responsible only for orchestration and report writing.

**Tech Stack:** Python 3.12, pytest, standard-library `re` and `statistics`.

## Global Constraints

- Work only on `feat/evaluation-quality` in `D:\AgenX\archigraph-kg-evaluation-quality`.
- Do not call real LLM, embedding, rerank, or write evaluation data to Neo4j.
- Do not rewrite the historical `evals/report.md` as if it were a new run.
- Update `evals/DEVLOG.md`; do not edit `tasks/todo.md` or merge to main.

---

### Task 1: Extract and test Markdown-aware sentence splitting

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/metrics.py`
- Create: `evals/tests/__init__.py`
- Create: `evals/tests/test_metrics.py`
- Modify: `evals/run_eval.py:140-144`

**Interfaces:**
- Produces: `split_assertion_sentences(text: str) -> list[str]`.
- Consumes: answer Markdown text from `eval_qa`.

- [ ] **Step 1: Write exact failing cases**

```python
from evals.metrics import split_assertion_sentences


def test_preserves_dotted_identifiers_versions_urls_and_citations():
    text = "Cytoscape.js 用于图谱 [1]。React 19.2 可用 [2]。详见 https://example.com/a.b [3]。"
    assert split_assertion_sentences(text) == [
        "Cytoscape.js 用于图谱 [1]。",
        "React 19.2 可用 [2]。",
        "详见 https://example.com/a.b [3]。",
    ]


def test_markdown_lists_are_independent_and_fences_are_ignored():
    text = "- 第一项 [1]\n- 第二项 [2]\n```ts\nconst x = 'no claim'\n```"
    assert split_assertion_sentences(text) == ["第一项 [1]", "第二项 [2]"]
```

- [ ] **Step 2: Prove the helper is missing**

Run: `conda run -n myself python -m pytest evals/tests/test_metrics.py -q`

Expected: import failure for `evals.metrics`.

- [ ] **Step 3: Implement the pure splitter**

In `evals/metrics.py`, use a private-use sentinel for dots matching `(?<=\w)\.(?=\w)`, skip fenced-code lines, strip Markdown list prefixes, split on newlines and real sentence terminals, then restore protected dots. Filter empty or pure-format fragments.

- [ ] **Step 4: Replace the inline regex**

Import `split_assertion_sentences` in `run_eval.py` and replace:

```python
sentences = [s.strip() for s in re.split(r"[。.！!？?\n]+", answer.text) if s.strip()]
```

with:

```python
sentences = split_assertion_sentences(answer.text)
```

- [ ] **Step 5: Verify and commit**

```powershell
conda run -n myself python -m pytest evals/tests/test_metrics.py -q
git add evals/__init__.py evals/metrics.py evals/tests evals/run_eval.py
git commit -m "fix(evals): make hallucination splitting markdown-aware"
```

### Task 2: Compute pooled and macro entity recall explicitly

**Files:**
- Modify: `evals/metrics.py`
- Modify: `evals/tests/test_metrics.py`
- Modify: `evals/run_eval.py:195-305`

**Interfaces:**
- Produces: `summarize_entity_recall(hit_counts: list[int], gold_counts: list[int]) -> tuple[float, float]` returning `(pooled, macro)`.
- Produces summary keys `entity_recall_pooled` and `entity_recall_macro`.

- [ ] **Step 1: Write a failing aggregation test**

```python
def test_entity_recall_reports_pooled_and_macro():
    pooled, macro = summarize_entity_recall([8, 1], [10, 2])
    assert pooled == 0.75
    assert macro == 0.65
```

- [ ] **Step 2: Implement deterministic aggregation**

Validate equal list lengths, return `(0.0, 0.0)` for no samples, compute pooled as total hits divided by total gold, and macro as the mean of each `hits / gold` value while treating zero-gold samples as `0.0`.

- [ ] **Step 3: Wire orchestration and report names**

Collect exact per-document hit and gold counts instead of reconstructing hits later from rounded recall. Replace `entity_recall` in summary/report with:

```python
"entity_recall_pooled": entity_recall_pooled,
"entity_recall_macro": entity_recall_macro,
```

Print and render two clearly named rows. Preserve the pooled metric as the hard-threshold comparison.

- [ ] **Step 4: Verify and commit**

```powershell
conda run -n myself python -m pytest evals/tests/test_metrics.py -q
git add evals/metrics.py evals/tests/test_metrics.py evals/run_eval.py
git commit -m "refactor(evals): expose pooled and macro recall"
```

### Task 3: Document the corrected metric semantics

**Files:**
- Modify: `docs/evaluation.md`
- Create: `evals/DEVLOG.md`

- [ ] **Step 1: Update evaluation documentation**

Document 87.7% as the historical pooled value and 86.6% as the historical macro average. State that `evals/report.md` is a 2026-07-03 snapshot whose old single label means pooled recall.

- [ ] **Step 2: Add the DEVLOG entry**

Create `evals/DEVLOG.md` with the required 2026-07-11 five-field template. Explain why dotted tokens caused false positives and why pooled/macro must be named separately.

- [ ] **Step 3: Run the workline gate**

```powershell
conda run -n myself python -m pytest evals/tests/test_metrics.py -q
conda run -n myself python -m py_compile evals/run_eval.py evals/metrics.py
git diff --check main...HEAD
```

Expected: all commands exit 0 and no LLM network calls occur.

- [ ] **Step 4: Commit and hand off**

```powershell
git add docs/evaluation.md evals/DEVLOG.md
git commit -m "docs(evals): clarify recall and hallucination metrics"
git status --short
```

Expected: clean worktree. Report commits and test results to the main agent.

