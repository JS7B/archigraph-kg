# Agentic RAG Correctness and Consistency Hardening

**Goal:** Improve follow-up question grounding, citation correctness, canonical graph use in QA, and conversation durability without expanding the Agent's tool authority or adding dependencies.

This plan is executed through fixed `feat/*` branches in sibling physical worktrees. The main checkout is the brain: it freezes the contract, reviews complete diffs, merges approved commits, updates project records, and performs final verification. Workers commit only on their own branches and never merge or push.

## Current baseline

- The ReAct planner sees the latest six conversation messages, but the separate final-answer generation call does not see history.
- Message embeddings are stored, but no semantic-history query exists. This plan keeps the six-message window and does not add long-term memory retrieval.
- Final citations are selected by a `[n]` regex, while confidence is calculated from every written marker, including invalid indices.
- The Wave 3 graph UI uses an accepted-only canonical projection, while `qa.expand_entities` still traverses document-scoped source `Entity/RELATES` facts.
- Conversation `next_turn` calculation and individual Message writes are separate operations; a concurrent turn or a failure between user/agent writes can create overwritten or partial history.

## Shared constraints

- No new dependency, environment variable, model name, endpoint, or frontend response field.
- Existing source `Entity`, `RELATES`, `MENTIONS`, `RESOLVES_TO`, and `CanonicalEntity` data must not be mutated by QA queries.
- Conversation CRUD and `POST /api/chat` response contracts remain compatible.
- The six-message history window remains the token boundary; semantic message retrieval, summaries, user profiles, and cross-conversation memory are non-goals.
- A prompt instruction alone is not acceptance evidence. Every new boundary requires deterministic tests.
- Real LLM tests are supplementary. Required worker gates use mocks/fakes and run without an external model.
- Real Neo4j tests use an isolated temporary database/container or precisely prefixed records with cleanup. They must not modify the personal graph.
- Existing untracked files in the main checkout are outside scope and must remain untouched.
- Every worker appends a five-field learning record to `backend/DEVLOG.md` when its implementation is non-trivial.

## Worktree and merge map

| Line | Branch | Sibling worktree | Purpose |
| --- | --- | --- | --- |
| A | `feat/audit-infrastructure` | `E:\Mine\archigraph-kg-agentic-audit` | Register branch scopes and deterministic gates |
| P | `feat/qa-memory-grounding` | `E:\Mine\archigraph-kg-qa-memory` | Resolve follow-up references and ground final synthesis in history |
| Q | `feat/qa-citation-guard` | `E:\Mine\archigraph-kg-qa-citation-guard` | Validate citation indices and confidence |
| S | `feat/conversation-atomic-turn` | `E:\Mine\archigraph-kg-conversation-atomic` | Atomically persist a complete conversation turn |
| R | `feat/qa-canonical-expand` | `E:\Mine\archigraph-kg-qa-canonical-expand` | Use accepted-only canonical relations in Agent graph expansion |

Merge order is fixed: **A → P → Q → S → R → final verification**.

Q and S may run in parallel after P is merged because their production file ownership is disjoint. R starts from the main commit containing Q and S because it may need to adjust Agent dispatch and must not race Q in `agent.py`.

## Wave 0 — A: audit infrastructure

### Required behavior

- Add exact branch scopes for P, Q, S, and R to `.codex/hooks/audit_gate.py`.
- Route each branch to its focused deterministic pytest suites plus compile/diff checks already supported by the gate.
- Update `backend/tests/audit/test_audit_gate.py` with allowed and forbidden path cases for every new branch.
- Update `docs/audit-workflow.md` with ownership and non-security-boundary wording.
- Keep the audit branch limited to audit implementation, audit tests, audit documentation, and its DEVLOG entry.

### Acceptance

- Audit tests pass.
- Each new branch accepts its declared production/test paths and rejects an unrelated path.
- Gate failures remain fail-closed and return valid JSON on Windows.

## Wave 1 — P: follow-up question grounding

### Required behavior

- Preserve `original_question` for user-facing answer semantics.
- When history is non-empty, create one standalone retrieval question that resolves references such as “它”“那个方案”“前一个”。The rewriter must be instructed to resolve references only, never answer the question or add facts. Strip the result and enforce a server-side 1,000-character maximum without adding configuration.
- When history is empty, do not make a rewrite call and preserve the existing single-turn path.
- An empty rewrite, timeout, unsupported response, or ordinary rewrite failure falls back to the original question and does not fail the Run.
- Perform the rewrite at most once per Run. Agentic execution and function-calling fallback must reuse the same result.
- Use the standalone question for retrieval planning. Final synthesis must receive the original question, the resolved standalone question, the same recent history, and the current evidence context.
- History remains context, not evidence. No-history/no-evidence behavior continues to return the fixed low-confidence refusal.
- Keep rewrite work inside the chat semaphore so it participates in the existing provider concurrency limit.

### Required tests

- No history causes zero rewrite calls and preserves current message construction.
- A pronoun follow-up produces the expected standalone question and that value reaches both Agentic and linear fallback retrieval paths.
- Final-answer messages contain history, original question, resolved question, and document context in the intended roles/order.
- Rewrite failure and empty output fall back exactly once to the original question.
- History never creates a Citation and an empty evidence pool still refuses.
- A mocked tool-calling `BadRequestError` does not trigger a second rewrite during linear fallback.

### Non-goals

- Message-vector retrieval, conversation summaries, cross-conversation memory, user profiles, or a new memory tool.
- Persisting the standalone rewrite as a separate user-visible Message.

## Wave 2 — Q: citation and confidence guard

### Required behavior

- Centralize answer finalization so Agentic and linear pipelines cannot diverge.
- Parse marker indices once and compute `valid_used = written_indices ∩ available_citation_indices`.
- Return only Citations referenced by valid indices, in deterministic context order.
- Calculate confidence from unique valid Citations, not raw written markers.
- Treat only the frozen citation syntax `[positive integer]` outside Markdown code spans/blocks as a marker. Remove `[0]` and indices beyond the available evidence range from returned Markdown without changing valid markers.
- If no valid Citation remains, replace the generated text with the standard low-confidence refusal rather than delivering an uncited factual answer.
- If valid and invalid markers are mixed, keep the sanitized answer but cap confidence at `medium`.
- Preserve the existing Answer/Citation API contract and clickable valid markers.

### Required tests

- Valid, duplicate, missing, zero, out-of-range, code-span, and fenced-code markers.
- Two invalid markers cannot produce high confidence.
- Mixed valid/invalid output keeps only valid Citations, removes invalid markers, and cannot be high confidence.
- No valid marker returns the fixed refusal.
- Agentic and linear pipelines use the same finalizer and produce identical results for the same text/context.
- Markdown code spans/blocks and ordinary bracketed numbers are not accidentally rewritten beyond the frozen citation syntax.

### Non-goals

- Claim-level entailment, a second verifier model, automatic citation repair, or similarity-based confidence calibration.

## Wave 2 — S: atomic conversation turn persistence

Q and S are independent workers and may execute in parallel.

### Required behavior

- Introduce a single `append_turn` storage operation that persists user and agent messages as one logical turn.
- Generate both message embeddings before opening the write transaction, preferably in one ordered embedding batch.
- Use one Neo4j managed write transaction to acquire a write lock on the Conversation, atomically advance a monotonic turn counter, allocate two adjacent turn indices, write both Messages, link them to the Conversation, and update `message_count`. Do not retain a separate `max(turn_index)+1` read as the allocator.
- Use `run_id` or an equivalent deterministic turn id as an idempotency key. Retrying the same completed Run must return the same pair without incrementing indices or duplicating/overwriting content.
- Concurrent distinct Runs targeting one Conversation must receive distinct, ordered turn pairs.
- Existing historical Messages remain readable; external consumers must continue to treat `message_id` as opaque.
- A missing supplied `conversationId` is rejected synchronously with 404 before a Run is created.
- Any transaction failure leaves neither message from the new turn committed. A deleted conversation causes a failed Run without a partial turn.

### Required tests

- Atomic happy path writes adjacent user/agent indices, citations, confidence, embeddings, links, and exact message count.
- Injected failure before commit leaves zero new Messages.
- Same idempotency key retried twice returns one pair and unchanged count.
- Concurrent distinct turn writes produce unique ordered indices and preserve both pairs.
- Existing old-format Messages remain listed in order.
- Unknown `conversationId` returns 404 and does not create a Run.
- `run_chat` emits succeeded only after the atomic turn is committed; persistence failure emits failed.

### Non-goals

- Multi-user ownership, distributed locks, an external task queue, message editing, or cancellation of already running tasks.

## Wave 3 — R: accepted-only canonical QA expansion

### Required behavior

- Keep Chunk vector retrieval unchanged. Replace only the graph-relation expansion behind `expand_entity`.
- Accept expansion chunk IDs only when they exist in the current Run's `evidence_pool`; invented or stale model-supplied IDs are ignored and reported as an empty/invalid tool observation.
- Starting from accepted entities mentioned by those Chunks, project only source facts whose two endpoints have valid accepted `RESOLVES_TO` evidence and whose `RELATES.evidence_chunk_id` is a valid same-document Chunk mentioning both source endpoints.
- Exclude review/unresolved endpoints, malformed resolution evidence, malformed relation evidence, and collapsed canonical self-relations.
- Aggregate duplicate source facts by directed canonical source, canonical target, and relation type. Final relation context must show one stable canonical path per key while retaining bounded provenance/support internally.
- Preserve direction and relation type. Do not create canonical `RELATES` edges or modify any source/canonical nodes.
- Keep the Answer/Citation contract chunk-based; graph paths remain auxiliary context rather than independent citations.

### Required tests

- Accepted relation round-trip from an evidence-pool Chunk.
- Review/unresolved endpoint, fake resolution evidence, fake relation evidence, single-endpoint mention, cross-document fact, and canonical self-relation are excluded.
- Two documents supporting the same canonical directed relation produce one stable path with support/provenance retained.
- Reverse direction and different relation types remain distinct.
- Model-supplied chunk IDs outside `evidence_pool` never reach the graph query.
- Input row order does not change path order or identity.
- A real Neo4j test proves query-only behavior with before/after fingerprints and zero canonical `RELATES`.
- Existing linear and Agentic QA tests continue to pass.

### Non-goals

- Changing vector recall to canonical entities, materializing canonical relations, exposing a new public graph API, or redesigning the graph frontend.

## Brain review and correction protocol

- Every worker reads this plan and `AGENTS.md`, writes failing tests first, edits only its declared scope, appends its local DEVLOG, commits, and reports its commit hash.
- The main brain reads `main...branch` in full, checks the commit scope and working-tree cleanliness, runs the branch gate, and returns blocking findings to the same worker/worktree.
- Fixes remain on the responsible branch. A separate `feat/qa-integration` worktree is created only if a real cross-branch defect cannot be assigned cleanly; it is not pre-created.
- Main alone merges. Workers never merge main, push, edit `tasks/todo.md`, or touch the user's untracked files.

## Final verification

After A, P, Q, S, and R are reviewed and merged:

1. Run `git diff --check` and audit tests.
2. Run the full backend non-LLM suite with configured Neo4j lifecycle coverage.
3. Run focused mocked Agent protocol tests and, when credentials are available, the real LLM follow-up test.
4. Run evaluation tests and confirm extraction/provenance metrics do not regress.
5. Run frontend lint, typecheck, Vitest, and build even though no frontend contract change is expected.
6. Query the personal graph read-only before/after QA smoke tests and confirm source/canonical fingerprints and canonical `RELATES=0` are unchanged.
7. Start Neo4j, backend, and frontend locally and manually verify:
   - a pronoun follow-up resolves the intended subject;
   - a generated answer contains only clickable valid citations;
   - a relation-assisted answer excludes review-only graph facts;
   - refreshing and reopening the conversation restores a complete ordered turn.
8. Update `tasks/todo.md`, project explanations, and the appropriate DEVLOG from main; then remove/prune every worker worktree and verify no worker process remains.

The goal is complete only when all four behaviors and the final integration gates pass. Near-completion, lack of live credentials, or completion of only the worker branches is not sufficient.
