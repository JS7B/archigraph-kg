import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { fetchCommunities, fetchGraph, fetchSubgraph } from '../../api/graph'
import { GraphView } from './GraphView'

vi.mock('../../api/graph', () => ({
  fetchCommunities: vi.fn(),
  fetchGraph: vi.fn(),
  fetchSubgraph: vi.fn(),
}))

vi.mock('cytoscape', () => {
  const collection = () => ({
    removeClass: vi.fn(),
    addClass: vi.fn(),
    filter: vi.fn(() => collection()),
    not: vi.fn(() => collection()),
    connectedEdges: vi.fn(() => collection()),
  })
  const cytoscape = vi.fn(() => ({
    resize: vi.fn(),
    fit: vi.fn(),
    destroy: vi.fn(),
    on: vi.fn(),
    nodes: vi.fn(() => collection()),
    edges: vi.fn(() => collection()),
  }))
  ;(cytoscape as typeof cytoscape & { use: ReturnType<typeof vi.fn> }).use = vi.fn()
  return { default: cytoscape }
})

vi.mock('cytoscape-fcose', () => ({ default: {} }))

const mockedFetchCommunities = vi.mocked(fetchCommunities)
const mockedFetchGraph = vi.mocked(fetchGraph)
const mockedFetchSubgraph = vi.mocked(fetchSubgraph)

beforeEach(() => {
  mockedFetchCommunities.mockReset()
  mockedFetchGraph.mockReset()
  mockedFetchSubgraph.mockReset()
})

it('starts with the first bounded community and local subgraph', async () => {
  mockedFetchCommunities.mockResolvedValue([
    {
      id: 'community-ent-a',
      representativeNode: {
        id: 'ent-a',
        label: 'A',
        entityType: 'Concept',
        documentId: 'doc-a',
      },
      nodeCount: 2,
      edgeCount: 1,
      documentIds: ['doc-a'],
    },
  ])
  mockedFetchSubgraph.mockImplementation(() => new Promise(() => undefined))
  mockedFetchGraph.mockImplementation(() => new Promise(() => undefined))

  render(<GraphView />)

  await waitFor(() => expect(mockedFetchCommunities).toHaveBeenCalled())
  expect(mockedFetchSubgraph).toHaveBeenCalledWith('ent-a')
  expect(screen.getByRole('button', { name: /A/ })).toBeInTheDocument()
  expect(screen.getByRole('status', { name: 'graph-subgraph-loading' })).toBeInTheDocument()
  expect(mockedFetchGraph).not.toHaveBeenCalled()
})

it('falls back to the existing entities endpoint when community loading fails', async () => {
  mockedFetchCommunities.mockRejectedValue(new Error('communities unavailable'))
  mockedFetchGraph.mockResolvedValue({ nodes: [], edges: [] })

  render(<GraphView />)

  await waitFor(() => expect(mockedFetchGraph).toHaveBeenCalled())
  expect(screen.getByRole('status', { name: 'graph-empty' })).toBeInTheDocument()
})
