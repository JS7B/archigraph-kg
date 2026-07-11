import { beforeEach, expect, it, vi } from 'vitest'
import { apiFetch } from './client'
import { fetchCommunities, fetchGraph, fetchSubgraph } from './graph'

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
