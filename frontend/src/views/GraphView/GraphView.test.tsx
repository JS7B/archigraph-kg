import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { fetchCommunities, fetchGraph, fetchSubgraph } from '../../api/graph'
import { GraphView } from './GraphView'
import { edgeConfidenceClass, nodeVisualClasses } from './graphVisuals'

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
    forEach: vi.fn(),
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

it('assigns stable visual classes for entity type, community, and edge confidence', () => {
  expect(
    nodeVisualClasses({
      id: 'node-a',
      label: 'Alpha',
      entityType: 'Library',
      communityId: 'community-1',
    }),
  ).toContain('type-library')
  expect(
    nodeVisualClasses({
      id: 'node-a',
      label: 'Alpha',
      entityType: 'Library',
      communityId: 'community-1',
    }),
  ).toContain('community-community-1')
  expect(
    nodeVisualClasses({
      id: 'node-a',
      label: 'Alpha',
      entityType: 'Library',
      communityId: 'community-1',
    }),
  ).toMatch(/community-palette-[0-3]/)
  expect(edgeConfidenceClass(0.9)).toBe('confidence-high')
  expect(edgeConfidenceClass(0.6)).toBe('confidence-medium')
  expect(edgeConfidenceClass(null)).toBe('confidence-unknown')
})

it('shows relation provenance and explicitly labels missing evidence', async () => {
  mockedFetchCommunities.mockResolvedValue([])
  mockedFetchGraph.mockResolvedValue({
    nodes: [
      { id: 'node-a', label: 'Alpha', entityType: 'Concept', documentId: 'doc-a' },
      { id: 'node-b', label: 'Beta', entityType: 'Concept', documentId: 'doc-b' },
    ],
    edges: [
      {
        id: 'node-a-node-b-RELATES',
        source: 'node-a',
        target: 'node-b',
        relationType: 'RELATES',
        confidence: 0.42,
        evidenceChunkId: null,
      },
    ],
  })

  render(<GraphView />)

  const alphaButton = (await screen.findAllByRole('button', { name: /Alpha/ }))[0]
  alphaButton.click()

  expect(await screen.findByText('Missing evidence')).toBeInTheDocument()
  expect(screen.getByText('doc-a')).toBeInTheDocument()
  expect(screen.getByText('0.42')).toBeInTheDocument()
})

it('keeps the selected entity in the keyboard list and returns focus to it', async () => {
  mockedFetchCommunities.mockResolvedValue([])
  mockedFetchGraph.mockResolvedValue({
    nodes: [{ id: 'node-a', label: 'Alpha', entityType: 'Concept' }],
    edges: [],
  })

  render(<GraphView />)
  const alphaButton = (await screen.findAllByRole('button', { name: /Alpha/ }))[0]
  fireEvent.click(alphaButton)

  expect(alphaButton).toHaveAttribute('aria-current', 'true')
  expect(document.activeElement).toBe(alphaButton)
})
