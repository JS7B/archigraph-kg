# Wave 1: Limited Extraction Concurrency and Graph Quality Baseline

**Goal:** Run two independent worktrees in parallel: reduce one-document extraction latency without changing graph semantics, and establish reproducible graph-quality measurements without changing production ingestion.

## Shared constraints

- Both branches start from the same refreshed `main` commit.
- Workers commit only on their fixed branches. They do not merge, push, or edit `tasks/todo.md`.
- No new dependency is allowed.
- Tests must be deterministic and must not require a live LLM or Neo4j.
- Existing untracked files in the main checkout are outside scope.

## P: `feat/kg-extraction`

Worktree: `E:\Mine\archigraph-kg-extraction`.

### Required behavior

- Extract at most three non-`SKIP` chunks concurrently within one document.
- Expose `max_workers` through the extraction pipeline with a default of 3; do not add an environment variable.
- Restore successful results and failures to original document chunk order before merge. Do not sort by string `chunk_id`.
- Preserve failure semantics: `ExtractionError` is isolated per chunk; unexpected exceptions still fail the document.
- Report progress after completion as `(completed, extractable_total)`; `SKIP` chunks are not submitted and are not included in the total.
- Preserve `max_attempts`, extraction policy, language, provenance, writer behavior, and current retry policy.

### Required tests

- Blocking fakes prove real overlap and a peak concurrency no greater than the configured limit.
- Deliberately out-of-order completions still return successes and failures in source order.
- `ExtractionError`, unexpected exception, `SKIP`, parameter forwarding, progress monotonicity, and pipeline forwarding are covered.
- Focused extraction tests and ingestion task tests pass.

### Non-goals

- Process-wide/provider-wide rate limiting.
- Retry-policy redesign, async OpenAI client, extraction cache, or graph-quality changes.

## Q: `feat/kg-evaluation`

Worktree: `E:\Mine\archigraph-kg-evaluation`.

### Required behavior

- Keep current pooled and macro recall behavior compatible.
- Extend labeled fixtures so metrics have reviewed positive and negative examples and a declared sample coverage.
- Report entity precision, relation semantic precision, and provenance completeness with explicit non-zero denominators for the labeled baseline.
- Add structural diagnostics for isolated entities, degree-one entities, low-confidence relations, cross-document normalized-name duplicates, component-size distribution, and suspicious generic hubs.
- Treat unmatched extracted items as review candidates, not automatically as errors.
- Keep metric functions deterministic and runnable without LLM or Neo4j. If live Neo4j reporting is supported, it must be an optional adapter with fixture-backed tests.
- Document definitions, denominators, sample coverage, and the distinction between semantic correctness and merely surviving merge.

### Required tests

- Every metric covers positive, negative, and empty input cases.
- Fixture validation rejects missing labels or provenance fields needed by a metric.
- The report has non-zero denominators for the reviewed baseline and provenance completeness is 100%.
- All `evals/tests` pass and changed Python files compile.

### Non-goals

- Production extraction, resolution, graph persistence, community detection, or frontend changes.
- Automatically treating every item absent from incomplete gold labels as noise.

## Brain review and merge gate

The main checkout reviews complete diffs and worker commits. Failed acceptance items return to the same worker/worktree. Merge P and Q only after their focused suites, audit gate, `git diff --check`, and clean worker status pass. After both merges, run the combined backend/evaluation regression set and update project task records from `main`.
