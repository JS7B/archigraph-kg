import { beforeEach, expect, it, vi } from 'vitest'
import { apiFetch } from './client'
import {
  fetchCanonicalCommunities,
  fetchCanonicalSubgraph,
  fetchCommunities,
  fetchGraph,
  fetchSubgraph,
  searchCanonicalEntities,
} from './graph'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const mockedApiFetch = vi.mocked(apiFetch)

beforeEach(() => {
  mockedApiFetch.mockReset()
})

it('maps bounded community summaries and query parameters', async () => {
  mockedApiFetch.mockResolvedValue([
    {
      id: 'community-ent-a',
      representativeNode: {
        id: 'ent-a',
        name: 'A',
        type: 'Concept',
        documentId: 'doc-a',
      },
      nodeCount: 2,
      edgeCount: 1,
      documentIds: ['doc-a'],
    },
  ])

  const result = await fetchCommunities({ limit: 4, nodeLimit: 12, documentId: 'doc-a' })

  expect(mockedApiFetch).toHaveBeenCalledWith(
    '/api/graph/communities?limit=4&nodeLimit=12&documentId=doc-a',
  )
  expect(result[0]?.representativeNode).toEqual({
    id: 'ent-a',
    label: 'A',
    entityType: 'Concept',
    documentId: 'doc-a',
  })
})

it('maps bounded subgraph metadata and edge evidence', async () => {
  mockedApiFetch.mockResolvedValue({
    centerId: 'ent-a',
    nodes: [
      { id: 'ent-a', name: 'A', type: 'Concept', documentId: 'doc-a' },
      { id: 'ent-b', name: 'B', type: 'Method', documentId: 'doc-a' },
    ],
    edges: [
      {
        source: 'ent-a',
        target: 'ent-b',
        type: 'uses',
        confidence: 0.91,
        evidenceChunkId: 'doc-a#0',
      },
    ],
    metadata: { depth: 2, limit: 8, nodeCount: 2, edgeCount: 1, truncated: false },
  })

  const result = await fetchSubgraph('ent-a', {
    depth: 2,
    limit: 8,
    type: 'Method',
    minConfidence: 0.7,
    documentId: 'doc-a',
  })

  expect(mockedApiFetch).toHaveBeenCalledWith(
    '/api/graph/entities/ent-a/subgraph?depth=2&limit=8&documentId=doc-a&type=Method&minConfidence=0.7',
  )
  expect(result.centerId).toBe('ent-a')
  expect(result.metadata.truncated).toBe(false)
  expect(result.edges[0]).toMatchObject({
    relationType: 'uses',
    confidence: 0.91,
    evidenceChunkId: 'doc-a#0',
  })
})

it('preserves evidence fields when mapping the existing graph endpoint', async () => {
  mockedApiFetch.mockResolvedValue({
    nodes: [{ id: 'ent-a', name: 'A', type: 'Concept', documentId: 'doc-a' }],
    edges: [
      {
        source: 'ent-a',
        target: 'ent-a',
        type: 'related',
        confidence: null,
        evidenceChunkId: null,
      },
    ],
  })

  const result = await fetchGraph()

  expect(result.edges[0]).toMatchObject({
    confidence: null,
    evidenceChunkId: null,
  })
})

it('maps the canonical community projection without inventing one document id', async () => {
  mockedApiFetch.mockResolvedValue({
    communities: [
      {
        id: 'community:v1:alpha',
        representativeNode: {
          id: 'canonical:v1:alpha',
          name: 'Alpha',
          type: 'Concept',
          identity: 'canonical',
          documentIds: ['doc-a', 'doc-b'],
          sourceEntityCount: 2,
          mentionCount: 4,
          aliases: ['Alpha', 'alpha framework'],
          aliasCount: 3,
          aliasesTruncated: true,
          degree: 2,
        },
        nodeCount: 3,
        edgeCount: 2,
        documentIds: ['doc-a', 'doc-b'],
        totalSupport: 4,
      },
    ],
    coverage: {
      sourceEntityCount: 5,
      acceptedSourceEntityCount: 4,
      reviewSourceEntityCount: 1,
      unresolvedSourceEntityCount: 0,
      sourceRelationCount: 4,
      projectedSourceRelationCount: 3,
      excludedRelationCount: 1,
      collapsedSelfRelationCount: 0,
    },
    metadata: {
      limit: 4,
      nodeLimit: 12,
      edgeLimit: 24,
      evidenceLimit: 6,
      nodeCount: 3,
      edgeCount: 2,
      evidenceCount: 4,
      communityCount: 1,
      truncated: false,
    },
  })

  const result = await fetchCanonicalCommunities({
    limit: 4,
    nodeLimit: 12,
    edgeLimit: 24,
    evidenceLimit: 6,
    documentId: 'doc-a',
    minConfidence: 0.7,
  })

  expect(mockedApiFetch).toHaveBeenCalledWith(
    '/api/graph/canonical/communities?limit=4&nodeLimit=12&edgeLimit=24&evidenceLimit=6&documentId=doc-a&minConfidence=0.7',
  )
  expect(result.communities[0]?.representativeNode).toEqual({
    id: 'canonical:v1:alpha',
    label: 'Alpha',
    entityType: 'Concept',
    identity: 'canonical',
    documentIds: ['doc-a', 'doc-b'],
    sourceEntityCount: 2,
    mentionCount: 4,
    aliases: ['Alpha', 'alpha framework'],
    aliasCount: 3,
    aliasesTruncated: true,
    degree: 2,
  })
  expect(result.communities[0]?.representativeNode.documentId).toBeUndefined()
  expect(result.coverage.reviewSourceEntityCount).toBe(1)
  expect(result.metadata.edgeLimit).toBe(24)
})

it('maps canonical aggregate edges, bounded evidence, coverage, and subgraph limits', async () => {
  mockedApiFetch.mockResolvedValue({
    centerId: 'canonical:v1:alpha',
    nodes: [
      {
        id: 'canonical:v1:alpha',
        name: 'Alpha',
        type: 'Concept',
        identity: 'canonical',
        documentIds: ['doc-a', 'doc-b'],
        sourceEntityCount: 2,
        mentionCount: 3,
        aliases: ['Alpha'],
        aliasCount: 1,
        aliasesTruncated: false,
        degree: 1,
      },
      {
        id: 'canonical:v1:beta',
        name: 'Beta',
        type: 'Method',
        identity: 'canonical',
        documentIds: ['doc-a', 'doc-b'],
        sourceEntityCount: 2,
        mentionCount: 2,
        aliases: ['Beta'],
        aliasCount: 1,
        aliasesTruncated: false,
        degree: 1,
      },
    ],
    edges: [
      {
        id: 'canonical-edge:v1:alpha-beta-uses',
        source: 'canonical:v1:alpha',
        target: 'canonical:v1:beta',
        type: 'uses',
        confidence: 0.93,
        supportCount: 2,
        evidenceCount: 3,
        evidence: [
          {
            chunkId: 'doc-a#0',
            documentId: 'doc-a',
            sourceEntityId: 'doc-a::alpha',
            targetEntityId: 'doc-a::beta',
            confidence: 0.93,
          },
          {
            chunkId: 'doc-b#1',
            documentId: 'doc-b',
            sourceEntityId: 'doc-b::alpha',
            targetEntityId: 'doc-b::beta',
            confidence: 0.8,
          },
        ],
        evidenceTruncated: true,
      },
    ],
    coverage: {
      sourceEntityCount: 5,
      acceptedSourceEntityCount: 4,
      reviewSourceEntityCount: 1,
      unresolvedSourceEntityCount: 0,
      sourceRelationCount: 4,
      projectedSourceRelationCount: 3,
      excludedRelationCount: 1,
      collapsedSelfRelationCount: 0,
    },
    metadata: {
      depth: 2,
      nodeLimit: 8,
      edgeLimit: 12,
      evidenceLimit: 2,
      nodeCount: 2,
      edgeCount: 1,
      evidenceCount: 3,
      truncated: true,
    },
  })

  const result = await fetchCanonicalSubgraph('canonical:v1:alpha', {
    depth: 2,
    nodeLimit: 8,
    edgeLimit: 12,
    evidenceLimit: 2,
    documentId: 'doc-a',
    minConfidence: 0.7,
  })

  expect(mockedApiFetch).toHaveBeenCalledWith(
    '/api/graph/canonical/entities/canonical%3Av1%3Aalpha/subgraph?depth=2&nodeLimit=8&edgeLimit=12&evidenceLimit=2&documentId=doc-a&minConfidence=0.7',
  )
  expect(result.edges[0]).toMatchObject({
    id: 'canonical-edge:v1:alpha-beta-uses',
    relationType: 'uses',
    supportCount: 2,
    evidenceCount: 3,
    evidenceTruncated: true,
  })
  expect(result.edges[0]?.evidence).toHaveLength(2)
  expect(result.metadata.evidenceLimit).toBe(2)
  expect(result.metadata.truncated).toBe(true)
})

it('maps canonical alias search and forwards its active evidence scope', async () => {
  mockedApiFetch.mockResolvedValue([
    {
      id: 'canonical:v1:alpha',
      name: 'Alpha',
      type: 'Concept',
      identity: 'canonical',
      documentIds: ['doc-a'],
      sourceEntityCount: 1,
      mentionCount: 2,
      aliases: ['A'],
      aliasCount: 1,
      aliasesTruncated: false,
      degree: 0,
    },
  ])

  const result = await searchCanonicalEntities('A', {
    limit: 7,
    documentId: 'doc-a',
  })

  expect(mockedApiFetch).toHaveBeenCalledWith(
    '/api/graph/canonical/search?q=A&limit=7&documentId=doc-a',
  )
  expect(result[0]).toMatchObject({
    id: 'canonical:v1:alpha',
    identity: 'canonical',
    aliases: ['A'],
    documentIds: ['doc-a'],
  })
})
