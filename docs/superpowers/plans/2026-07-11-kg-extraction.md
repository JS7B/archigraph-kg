# Knowledge Graph Extraction Quality Implementation Plan

**Goal:** 保留现有 OpenAI-compatible 抽取管线，但把“LLM 自由输出直接入图”改成内容策略驱动、结构化校验、证据可追溯和关系端点治理的候选管线。

**Branch:** `feat/kg-extraction` in `D:\AgenX\archigraph-kg-extraction`.

## Constraints

- 不引入新的 LLM/图数据库框架；继续使用现有 Pydantic 与 Neo4j writer。
- `ContentKind`/`ExtractionPolicy` 来自 parsing；`SKIP` chunk 不调用 LLM，`SPECIALIZED` chunk 进入保守的代码策略。
- 每个候选实体/关系都必须带 `chunk_id` 和证据文本或证据区间；证据缺失只进入 review/rejected，不得写入 accepted 图。
- 保持现有 `DocumentExtraction`/writer API 可兼容；必要字段用默认值迁移。
- 任务只修改 `backend/app/extraction/`、对应 extraction tests 和 `backend/DEVLOG.md`，不改 parsing、graph、routers、frontend、`tasks/todo.md`。

## Task 1: candidate/evidence contract

Files: `models.py`, new `validation.py`, extraction tests.

- Add decision/status (`accepted`, `review`, `rejected`) and evidence model with source chunk and bounded text/offsets.
- Add strict validation helpers for entity type allowlist, non-empty names, relation endpoint membership, confidence range, and evidence presence.
- Preserve `ExtractedEntity`/`ExtractedRelation` input compatibility while making normalized candidates explicit.
- Tests cover malformed JSON-shaped models, missing evidence, unknown types, empty names, dangling endpoints.

## Task 2: policy-aware extraction and structured output

Files: `extractor.py`, `llm_extract.py`, `pipeline.py`, `prompt.py`, tests.

- Skip `ExtractionPolicy.SKIP` chunks without an LLM call.
- Add bounded code/config prompts and strict JSON/Pydantic validation; unknown/invalid output becomes a failure/review result rather than a graph write.
- Preserve chunk provenance when converting model output to candidates.
- Tests use fake clients to prove skip behavior, malformed output handling, and code-noise suppression.

## Task 3: merge/relation governance

Files: `merge.py`, `writer.py`, tests.

- Merge only accepted candidates; keep review/rejected diagnostics available to stats.
- Enforce relation endpoint membership and minimum confidence/semantic type allowlist before `MergedRelation`.
- Preserve evidence chunk IDs and bounded provenance; deduplicate deterministic duplicates.
- Tests cover generic noun rejection, dangling relations, confidence tie behavior, and evidence round-trip to writer payloads.

## Task 4: integration contract and learning log

Files: extraction public exports/tests, `backend/DEVLOG.md`.

- Expose the new candidate/status/evidence contract without breaking existing callers.
- Add a five-field DEVLOG entry explaining why extraction is staged as candidate → validation → merge → write.
- Run extraction unit command (`pytest backend/tests/extraction -q --confcutdir=backend/tests/extraction --ignore=backend/tests/extraction/test_writer.py --ignore=backend/tests/extraction/test_llm_real.py`), py_compile, diff-check, and the Hook.

## Acceptance

- No accepted entity/relation lacks chunk provenance.
- No `SKIP` chunk invokes the LLM.
- Invalid/unknown output cannot reach Neo4j writer.
- Existing extraction unit suite remains green; integration writer tests remain separately runnable with configured Neo4j.
