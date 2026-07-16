# Wave 3: Canonical Projection and Community Experience

**Goal:** Make the graph workspace consume a provenance-preserving canonical projection so cross-document identities, aggregated relation evidence, deterministic communities, and local exploration reflect the accepted Wave 2 overlay instead of the document-scoped source graph.

**Backend branch:** `feat/kg-community-api` in `E:\Mine\archigraph-kg-community-api`.

**Frontend branch:** `feat/graph-experience` in `E:\Mine\archigraph-kg-graph-experience`.

## Baseline and decision from Wave 2

- The source graph remains `Document → Chunk → Entity -[:RELATES]-> Entity`.
- Wave 2 added accepted-only `Entity -[:RESOLVES_TO]-> CanonicalEntity`; review and unresolved entities have no accepted link.
- The current graph APIs still query source `Entity/RELATES`, so review entities and cross-document duplicates still enter communities and local graphs.
- The current community endpoint computes connected components over a bounded source snapshot. A connected component is not a topic community and its lexicographically first source ID is not a meaningful representative.
- The current frontend silently falls back from a failed community request to the source entity graph, which would conceal a broken canonical projection.
- The current personal graph contains 138 source entities and 89 source relations. Wave 2 has 121 accepted sources and 17 review sources. Of the 89 source relations, 67 have accepted canonical endpoints plus valid relation evidence; the other 22 are excluded by endpoint review. All 67 eligible facts currently project to 67 directed canonical edge keys.

Wave 3 uses **read-time projection**. It must never persist `CanonicalEntity-[:RELATES]->CanonicalEntity` or rewrite source `RELATES`.

Read-time projection is required because alias correction, resolution reassignment, and document deletion already update the source graph and `RESOLVES_TO`. A materialized aggregate edge would otherwise retain stale support or evidence when a source document disappears while both canonical endpoints still exist.

QA and retrieval continue to read the source layer in this wave. Wave 3 changes graph exploration only.

## Canonical projection contract

### Eligible source facts

A source relation participates only when all of the following are true:

1. Both source `Entity` endpoints have an accepted `RESOLVES_TO`.
2. Each resolution edge still points to a real `Document → Chunk → MENTIONS → Entity` evidence chain matching its stored document and chunk IDs.
3. `RELATES.evidence_chunk_id` identifies a real Chunk in the source document.
4. The relation evidence Chunk `MENTIONS` both source endpoints.
5. The source and target entities belong to the same relation source document.
6. `documentId` and `minConfidence` filters are applied before aggregation.
7. When both endpoints resolve to the same canonical ID, the source fact is counted as a collapsed self relation but is not rendered as a normal edge.

Review/unresolved endpoints, missing evidence, cross-document evidence, and malformed resolution evidence never enter the canonical graph.

### Aggregated node

A canonical node is computed from accepted source entities in the active evidence scope and returns:

- `id`, `name`, `type`, and `identity = "canonical"`;
- stable sorted `documentIds`;
- `sourceEntityCount`;
- summed `mentionCount`;
- stable sorted, bounded `aliases`, plus `aliasCount` and `aliasesTruncated`;
- projected `degree`.

Do not invent a single `documentId` for a cross-document canonical.

### Aggregated directed edge

Aggregate by the directed key:

```text
(source_canonical_id, target_canonical_id, relation_type)
```

Reverse directions and different relation types remain distinct.

Each edge returns:

- a deterministic `canonical-edge:v1:<digest>` ID derived from the complete directed key;
- `source`, `target`, and `type`;
- compatibility `confidence`, explicitly defined as the maximum confidence among eligible source facts;
- `supportCount`;
- `evidenceCount`;
- stable sorted, bounded `evidence`;
- `evidenceTruncated`.

Each evidence record contains:

- `chunkId`;
- `documentId`;
- `sourceEntityId`;
- `targetEntityId`;
- the original source-fact `confidence`.

Evidence is sorted by document ID, chunk ID, source entity ID, and target entity ID. A response must never truncate evidence without returning the total count and `evidenceTruncated = true`.

### Projection coverage

Canonical overview and subgraph responses expose the active scope:

- `sourceEntityCount`;
- `acceptedSourceEntityCount`;
- `reviewSourceEntityCount`;
- `unresolvedSourceEntityCount`;
- `sourceRelationCount`;
- `projectedSourceRelationCount`;
- `excludedRelationCount`;
- `collapsedSelfRelationCount`.

This makes it explicit that review entities were withheld rather than silently lost.

## Backend API

Keep every existing source endpoint unchanged for compatibility and diagnostics. Add an explicit canonical namespace:

- `GET /api/graph/canonical/communities`
- `GET /api/graph/canonical/entities/{canonical_id}/subgraph`
- `GET /api/graph/canonical/search`

Do not infer identity from an ID shape and do not make one route sometimes return source IDs and sometimes canonical IDs.

### Canonical community overview

Accepted query parameters:

- `limit` (1–100);
- `nodeLimit` (1–500);
- `edgeLimit` (1–1000);
- `evidenceLimit` (1–20);
- optional `documentId`;
- optional `minConfidence` (0–1).

The response is an object containing `communities`, `coverage`, and bounded/truncated metadata.

Community detection is a deterministic, dependency-free, single-level modularity local-moving partition over the undirected form of the projected graph, weighted by `supportCount`. It is not a connected-component alias.

- Iterate nodes in canonical-ID order.
- Resolve equal modularity gains by canonical ID.
- Stop on convergence or a fixed iteration bound.
- Community ID is `community:v1:<digest>` of the stable sorted member IDs.
- Representative node is selected by projected weighted degree, then source entity count, then canonical ID.
- Communities are ordered by node count descending, total support descending, then community ID.
- Isolated accepted canonicals are excluded from the default community list but remain visible in coverage/search.

### Canonical local subgraph

Accepted query parameters:

- `depth` (1–4);
- `nodeLimit` (1–100);
- `edgeLimit` (1–200);
- `evidenceLimit` (1–20);
- optional `documentId`;
- optional `minConfidence` (0–1).

Run deterministic, bounded BFS over the read-time projected adjacency. The response contains `centerId`, canonical nodes, aggregated edges, coverage, and metadata including node/edge/evidence limits and `truncated`.

The center must be an accepted canonical in the active scope. A missing or out-of-scope center returns 404.

### Canonical search

Search canonical name plus names of accepted source entities in the active document scope. Return canonical nodes in stable order. This endpoint is available for later global-search UI work; the Wave 3 GraphView search box remains an explicitly labelled current-subgraph highlighter.

### Backend implementation boundary

Preferred files:

- add `backend/app/graph/projection.py`;
- modify `backend/app/graph/models.py`;
- modify `backend/app/routers/graph.py`;
- add `backend/tests/graph/test_canonical_projection.py`;
- add focused canonical API tests under `backend/tests/graph/`;
- append `backend/DEVLOG.md`.

Do not modify:

- `backend/app/resolution/**`;
- `backend/app/extraction/**`;
- `backend/app/runs/tasks.py`;
- `backend/app/qa/**`;
- `backend/app/graph/schema.py`;
- dependencies or environment files.

The existing `feat/kg-community-api` audit scope is authoritative.

## Frontend graph experience

The default GraphView consumes only the canonical namespace.

- Add typed `fetchCanonicalCommunities`, `fetchCanonicalSubgraph`, and canonical search mapping as needed.
- Remove automatic source-graph fallback from the canonical loading path. A canonical API failure shows a recoverable error and retains no fabricated/source replacement data.
- Represent nodes with `documentIds`, source count, aliases, and canonical identity.
- Use the stable backend edge ID and render support/evidence counts.
- Relation detail displays every returned evidence item with document, chunk, source endpoints, and confidence; truncation is explicit.
- Show a concise coverage notice such as “121 accepted / 17 review; review entities are not included in this canonical graph.”
- Label the structure as canonical graph and topic communities. Label the search field as current-subgraph search.
- Preserve the keyboard entity list and visible focus states; information cannot rely on color alone.
- Reuse the existing dark design tokens and visual language. Do not introduce a new palette, font, icon library, or ornamental redesign.

### Async and layout correctness

- Guard refresh/community/subgraph requests with a generation token or equivalent cancellation so stale responses cannot overwrite a newer selection.
- Commit selected community and center only with the matching successful response.
- A successful graph replacement clears stale selected node/edge state; an error does not relabel the old graph as the new community.
- Partition position caches by canonical scope/community instead of sharing one global node-position map.
- Reusing a populated scope uses stored/preset positions so toggling visibility does not reshuffle the graph.
- Switching community resets current-subgraph search and applies a separate layout scope.

### Frontend implementation boundary

Preferred files:

- `frontend/src/types/graph.ts`;
- `frontend/src/api/graph.ts`;
- `frontend/src/api/graph.test.ts`;
- `frontend/src/views/GraphView/**`;
- `frontend/DEVLOG.md`.

Do not change dependencies, lock files, unrelated views, backend files, or Agent animation state.

The existing `feat/graph-experience` audit scope is authoritative. Existing declared development dependencies may be restored from the lock file locally, but package manifests and lock files must remain unchanged.

## Required tests

### Backend pure/fake-driver tests

- Two documents supporting one canonical pair/type produce one directed edge with support two and two stable evidence records.
- Reverse direction and different relation types remain separate.
- Input row ordering does not change edge IDs, evidence order, community IDs, representatives, or response order.
- Review/unresolved endpoints never project.
- Missing, cross-document, single-endpoint mention, and malformed resolution evidence are excluded by query contract.
- Document and confidence filtering occur before aggregation.
- Self relations are omitted and counted in coverage.
- Evidence limit, node limit, edge limit, depth, and truncation are exact.
- The modularity partition splits a bridge-connected graph into deterministic topic communities rather than returning one connected component.
- Search matches canonical names and accepted source aliases.
- Existing source graph endpoints remain compatible.

### Backend real Neo4j tests

Use only `test_wave3_*` source/canonical data with precise cleanup.

- Cross-document canonical aggregation and evidence round-trip.
- Alias reassignment changes projected endpoints without changing source `RELATES`.
- Deleting one supporting document decreases support/evidence while preserving remaining support; deleting the final support removes the projected edge.
- API calls are read-only: source Entity, MENTIONS, RELATES, RESOLVES_TO, and canonical node fingerprints are unchanged.
- No canonical `RELATES` exists before or after projection queries.

### Frontend API/component tests

- Canonical node, edge, evidence, coverage, and bounds map exactly.
- Initial load calls only canonical endpoints; canonical failure never calls `fetchGraph`.
- Coverage, multi-evidence, missing/truncated states are readable.
- Rapid community switches cannot be overwritten by an older response.
- Successful graph replacement clears stale node/edge detail.
- Position caches are scope-partitioned and visibility toggles do not randomize a populated scope.
- Keyboard entity selection and focus remain available.
- Loading, error, empty, and 404 states are explicit and offer refresh/retry.
- Existing non-graph frontend behavior does not regress.

## Verification gates

Backend worker:

- graph/router focused tests;
- real Neo4j canonical lifecycle tests against an isolated temporary container or precisely prefixed shared records;
- `compileall`;
- `git diff --check`;
- `audit_gate.py`.

Frontend worker:

- lint;
- typecheck;
- Vitest;
- build;
- `git diff --check`;
- `audit_gate.py`.

Main checkout:

- review complete diffs and return all blocking findings to the same worker;
- merge backend first, then frontend;
- run full non-LLM backend regression, evaluation tests, frontend four-gate suite, and audit tests;
- query the real personal graph and verify the expected 121 accepted / 17 review scope, 67 eligible source facts, zero canonical RELATES, stable source fingerprints, deterministic communities, and bounded evidence;
- run the local UI and visually verify desktop plus narrow responsive layouts before recording completion.

## Worker and brain protocol

- Each worker uses its fixed branch/worktree, reads this plan and `AGENTS.md`, writes failing tests first, changes only allowed files, appends its local DEVLOG, commits, and never merges or pushes.
- Frontend implementation follows the existing design tokens plus the `ui-ux-pro-max` accessibility, state-clarity, loading, focus, and responsive checks; it does not redesign unrelated surfaces.
- Main is the only merge authority. Missing evidence, silent source fallback, unbounded projection, request races, misleading single-document fields, unstable community IDs, or source-graph mutation are blocking findings.
