# Wave 2: Canonical Entity Overlay

**Goal:** Persist deterministic cross-document entity resolution without replacing the document-scoped source graph or weakening provenance and document deletion.

**Branch:** `feat/kg-resolution` in `E:\Mine\archigraph-kg-resolution`.

## Decision from Wave 1

Wave 1 established metric semantics with a two-slice reviewed fixture. It did not produce a representative live-model precision snapshot, so this wave does not change extraction prompts or filtering rules. Conditional extraction-quality goal X remains deferred until a real reviewed run supplies evidence.

## Graph contract

- Keep `Document`, `Chunk`, `Entity`, `MENTIONS`, and source `RELATES` unchanged. Existing QA and graph APIs continue reading that source layer.
- Add only `(:Entity)-[:RESOLVES_TO]->(:CanonicalEntity)` as the accepted canonical overlay. Never add the `Entity` label to a canonical node.
- `CanonicalEntity` stores `canonical_id`, `canonical_name`, `normalized_name`, `entity_type`, and `resolution_version`. It does not cache document IDs, chunk IDs, aliases, counts, or projected relations; those values would become stale after deletion.
- Add a unique constraint for `canonical_id` and a non-unique lookup index for `normalized_name` through `ensure_schema`. The normalized name cannot be unique because a future manual split must be able to represent exact-name homonyms.
- `RESOLVES_TO` means accepted only. Store `method`, `score`, `reason`, `source_document_id`, and one real `evidence_chunk_id` that is already connected to the source entity by `MENTIONS`.
- Review or unresolved entities do not get `RESOLVES_TO`. Persist their status, method, score, reason, and stable sorted `candidate_canonical_ids` on the source `Entity` for later inspection. Exact/alias collisions and fuzzy ties must retain all review candidates instead of discarding their IDs.
- Do not create canonical `RELATES` edges in this wave. Wave 3 will project source relations onto accepted canonical endpoints.

## Stable identity and resolution rules

- Normalize with the existing Unicode/case/punctuation/whitespace rule.
- Bootstrap IDs are deterministic: `canonical:v1:` plus SHA-256 of the normalized name. Entity type is descriptive, not part of identity, because extraction type can drift across documents; this preserves the existing project decision to merge same-name entities despite type variation.
- Existing exact and explicit-alias matches are accepted with evidence. A new non-empty normalized name with a real mention bootstraps one canonical entity and is accepted with method `bootstrap`.
- Fuzzy matches, exact-key collisions, and ambiguous aliases remain `review`; they never bootstrap a competing canonical and never create an accepted edge.
- Missing mention provenance remains unresolved. Do not invent `unattributed` evidence for persistence.
- Exact same-name homonyms are a known boundary of deterministic bootstrap. A future manual split can create a canonical with an explicit override/suffixed ID but the same normalized name; the non-unique index permits this, after which the collision rule must return review rather than choose silently.

## Registry, write, and runtime integration

- Load canonical references from `CanonicalEntity`. Reconstruct aliases only from already accepted source links whose `RESOLVES_TO.method = 'alias'` and whose evidence chunk really mentions that source entity.
- The service and backfill function accept optional `Iterable[AliasRecord]` for first-time explicit aliases. Each record must identify an existing source entity, source document, real mentioning chunk, and existing target canonical before it can enter the resolver. The CLI may load the same records from an optional JSONL path. Provenance-free alias mappings are forbidden.
- Resolve records in stable source order. A bootstrap canonical is registered immediately so later matching entities in the same backfill resolve to it.
- Before writing a decision, remove the source entity's previous `RESOLVES_TO`; then write at most one accepted link or review metadata. Repeated execution must be idempotent.
- Persistence consumes an explicit source record containing `source_document_id`. Runtime receives `doc.document_id`; backfill reads `Entity.document_id`. It must not infer provenance with `entity_id.split('::')`; the existing pure adapter's legacy convenience behavior is not authoritative for writes.
- Cypher must match `(evidence:Chunk)-[:MENTIONS]->(source)` before creating an accepted edge. Accepted writes clear stale review properties; review/unresolved writes delete any old accepted link. Accepted-to-review and review-to-accepted transitions are both supported.
- Integrate resolution after the existing source extraction writer. Append resolution diagnostics to `ExtractionStats.diagnostics` without changing source entity/relation counts.
- Resolution failure remains an ingestion failure; rerunning is safe because source and canonical writes are idempotent.

## Backfill and deletion

- Provide an internal function and CLI command, runnable from `backend/` as `python -m app.resolution.backfill`, that reads every source `Entity` plus real incoming mentions and explicit `document_id` in stable `entity_id` order, resolves them through the registry, writes decisions, and removes orphan canonicals. The CLI may accept `--aliases <jsonl>` for provenance-carrying first-time aliases.
- Backfill must not call an LLM, reparse documents, or rewrite source `RELATES`.
- Keep document deletion in one Cypher transaction. Deleting source entities detaches their accepted links, then deletes only canonical nodes with no remaining incoming `RESOLVES_TO`.
- Deleting document A must preserve a canonical still supported by document B. Deleting the final source must remove the orphan canonical.

## Allowed files

- `backend/app/resolution/**`
- `backend/tests/resolution/**`
- `backend/app/extraction/pipeline.py`
- `backend/tests/extraction/test_contract.py`
- `backend/app/graph/schema.py`
- `backend/app/runs/tasks.py`
- `backend/tests/runs/test_tasks.py`
- `backend/DEVLOG.md`

No frontend, graph-router, QA, source writer, task list, environment, dependency, or lock-file changes are allowed.

## Required tests

- Canonical ID is stable across case, Unicode, punctuation, repeated runs, and entity-type drift.
- Two document-scoped entities with the same normalized name produce one canonical and two accepted links.
- Explicit alias resolves only when reconstructed from accepted provenance; fuzzy/ambiguous candidates remain review with no link.
- First-time explicit alias evidence is validated against source Entity/Document/MENTIONS and target CanonicalEntity; the next run can reconstruct it from the accepted alias edge, and deleting the alias source removes that alias mapping.
- Missing mentions cannot create accepted evidence or a canonical link.
- Reprocessing replaces an old source link, writes at most one target, and cleans an orphan target.
- Exact/alias collisions and fuzzy ties persist stable sorted candidate ID lists; accepted-to-review and review-to-accepted transitions clear the opposite state.
- Backfill is deterministic and idempotent and leaves source `Entity`, `MENTIONS`, and `RELATES` unchanged.
- Pipeline calls canonical persistence after the source writer and preserves diagnostics.
- Schema constraints exist.
- Delete A keeps B's canonical; deleting B removes it.
- Existing resolution, extraction, graph, runs, QA, and deletion behavior does not regress.

Unit tests use fake drivers or pure models. The worker may add optional real-Neo4j resolution tests that skip cleanly when configuration or the container is unavailable. The main checkout must run the live schema/backfill/delete path before merge completion.

## Worker and brain protocol

- The worker reads this plan and `AGENTS.md`, writes failing tests first, changes only the allowed files, appends `backend/DEVLOG.md`, commits on `feat/kg-resolution`, and does not merge or push.
- The main checkout reviews the complete diff and test coverage. Missing acceptance evidence returns to the same worker and worktree.
- After merge, the main checkout runs backfill against the local graph, verifies counts and provenance, runs the non-LLM backend regression, updates `tasks/todo.md`, removes the worktree, and prunes the merged local branch.
