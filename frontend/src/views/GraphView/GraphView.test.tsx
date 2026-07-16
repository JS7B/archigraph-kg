import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/client'
import {
  fetchCanonicalCommunities,
  fetchCanonicalSubgraph,
  fetchGraph,
} from '../../api/graph'
import type {
  CanonicalCommunityOverview,
  CanonicalSubgraph,
  GraphCommunity,
  GraphNode,
  ProjectionCoverage,
} from '../../types'
import { GraphView } from './GraphView'
import { edgeConfidenceClass, nodeVisualClasses } from './graphVisuals'

const cytoscapeLayouts = vi.hoisted(() => [] as string[])

vi.mock('../../api/graph', () => ({
  fetchCanonicalCommunities: vi.fn(),
  fetchCanonicalSubgraph: vi.fn(),
  fetchGraph: vi.fn(),
}))

vi.mock('cytoscape', () => {
  interface MockElement {
    data?: { id?: string; source?: string }
    position?: { x: number; y: number }
  }

  function collection(elements: MockElement[] = []) {
    const api = {
      removeClass: vi.fn(),
      addClass: vi.fn(),
      filter: vi.fn(() => collection()),
      not: vi.fn(() => collection()),
      connectedEdges: vi.fn(() => collection()),
      forEach: vi.fn(
        (
          callback: (node: {
            id: () => string
            position: () => { x: number; y: number }
          }) => void,
        ) => {
          elements.forEach((element, index) => {
            callback({
              id: () => String(element.data?.id ?? ''),
              position: () => element.position ?? { x: 40 + index * 20, y: 60 + index * 20 },
            })
          })
        },
      ),
    }
    return api
  }

  const cytoscape = vi.fn(
    (options: { elements?: MockElement[]; layout?: { name?: string } }) => {
      cytoscapeLayouts.push(options.layout?.name ?? 'unknown')
      const elements = options.elements ?? []
      const nodeElements = elements.filter((element) => !element.data?.source)
      const edgeElements = elements.filter((element) => element.data?.source)
      return {
        resize: vi.fn(),
        fit: vi.fn(),
        destroy: vi.fn(),
        on: vi.fn(),
        nodes: vi.fn(() => collection(nodeElements)),
        edges: vi.fn(() => collection(edgeElements)),
      }
    },
  )
  ;(cytoscape as typeof cytoscape & { use: ReturnType<typeof vi.fn> }).use = vi.fn()
  return { default: cytoscape }
})

vi.mock('cytoscape-fcose', () => ({ default: {} }))

const mockedFetchCanonicalCommunities = vi.mocked(fetchCanonicalCommunities)
const mockedFetchCanonicalSubgraph = vi.mocked(fetchCanonicalSubgraph)
const mockedFetchGraph = vi.mocked(fetchGraph)

const coverage: ProjectionCoverage = {
  sourceEntityCount: 5,
  acceptedSourceEntityCount: 4,
  reviewSourceEntityCount: 1,
  unresolvedSourceEntityCount: 0,
  sourceRelationCount: 3,
  projectedSourceRelationCount: 2,
  excludedRelationCount: 1,
  collapsedSelfRelationCount: 0,
}

function node(id: string, label: string, overrides: Partial<GraphNode> = {}): GraphNode {
  return {
    id,
    label,
    entityType: 'Concept',
    identity: 'canonical',
    documentIds: ['doc-a'],
    sourceEntityCount: 1,
    mentionCount: 1,
    aliases: [label],
    aliasCount: 1,
    aliasesTruncated: false,
    degree: 1,
    ...overrides,
  }
}

function community(id: string, representativeNode: GraphNode): GraphCommunity {
  return {
    id,
    representativeNode,
    nodeCount: 2,
    edgeCount: 1,
    totalSupport: 1,
    documentIds: representativeNode.documentIds ?? [],
  }
}

function overview(communities: GraphCommunity[]): CanonicalCommunityOverview {
  return {
    communities,
    coverage,
    metadata: {
      limit: 20,
      nodeLimit: 200,
      edgeLimit: 400,
      evidenceLimit: 20,
      communityCount: communities.length,
      nodeCount: communities.reduce((total, item) => total + item.nodeCount, 0),
      edgeCount: communities.reduce((total, item) => total + item.edgeCount, 0),
      evidenceCount: communities.reduce(
        (total, item) => total + (item.totalSupport ?? 0),
        0,
      ),
      truncated: false,
    },
  }
}

function subgraph(
  center: GraphNode,
  other: GraphNode = node('canonical:v1:beta', 'Beta'),
): CanonicalSubgraph {
  return {
    centerId: center.id,
    nodes: [center, other],
    edges: [
      {
        id: `canonical-edge:v1:${center.id}-${other.id}`,
        source: center.id,
        target: other.id,
        relationType: 'uses',
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
    coverage,
    metadata: {
      depth: 1,
      nodeLimit: 50,
      edgeLimit: 100,
      evidenceLimit: 20,
      nodeCount: 2,
      edgeCount: 1,
      evidenceCount: 3,
      truncated: true,
    },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  mockedFetchCanonicalCommunities.mockReset()
  mockedFetchCanonicalSubgraph.mockReset()
  mockedFetchGraph.mockReset()
  cytoscapeLayouts.length = 0
})

afterEach(cleanup)

it('loads only the canonical overview and first topic community', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([community('community:v1:alpha', alpha)]),
  )
  mockedFetchCanonicalSubgraph.mockImplementation(() => new Promise(() => undefined))

  render(<GraphView />)

  await waitFor(() => expect(mockedFetchCanonicalCommunities).toHaveBeenCalledTimes(1))
  expect(mockedFetchCanonicalSubgraph).toHaveBeenCalledWith(alpha.id)
  expect(screen.getByRole('button', { name: /Alpha/ })).toBeInTheDocument()
  expect(screen.getByRole('status', { name: 'graph-subgraph-loading' })).toBeInTheDocument()
  expect(mockedFetchGraph).not.toHaveBeenCalled()
})

it('shows a recoverable canonical error without falling back to the source graph', async () => {
  mockedFetchCanonicalCommunities.mockRejectedValue(
    new ApiError('upstream', 'canonical projection unavailable'),
  )

  render(<GraphView />)

  const error = await screen.findByRole('alert', { name: 'graph-error' })
  expect(error).toHaveTextContent('canonical projection unavailable')
  expect(screen.getByRole('button', { name: '重试加载规范图' })).toBeInTheDocument()
  expect(mockedFetchGraph).not.toHaveBeenCalled()
})

it('shows an explicit canonical empty state without fabricating source nodes', async () => {
  mockedFetchCanonicalCommunities.mockResolvedValue({
    ...overview([]),
    coverage: {
      ...coverage,
      sourceEntityCount: 0,
      acceptedSourceEntityCount: 0,
      reviewSourceEntityCount: 0,
      sourceRelationCount: 0,
      projectedSourceRelationCount: 0,
      excludedRelationCount: 0,
    },
  })

  render(<GraphView />)

  expect(await screen.findByRole('status', { name: 'graph-empty' })).toHaveTextContent(
    '还没有可展示的规范实体',
  )
  expect(screen.getByRole('button', { name: '刷新规范图' })).toBeInTheDocument()
  expect(mockedFetchCanonicalSubgraph).not.toHaveBeenCalled()
  expect(mockedFetchGraph).not.toHaveBeenCalled()
})

it('renders projection coverage and every returned aggregate evidence item', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha', {
    documentIds: ['doc-a', 'doc-b'],
    sourceEntityCount: 2,
    mentionCount: 4,
    aliases: ['Alpha', 'A'],
    aliasCount: 3,
    aliasesTruncated: true,
  })
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([community('community:v1:alpha', alpha)]),
  )
  mockedFetchCanonicalSubgraph.mockResolvedValue(subgraph(alpha))

  render(<GraphView />)

  expect(await screen.findByText(/4 个来源实体已解析/)).toBeInTheDocument()
  expect(screen.getByText(/1 个待审核实体未进入规范图/)).toBeInTheDocument()

  fireEvent.click(await screen.findByRole('button', { name: '选择规范实体 Alpha' }))

  expect(await screen.findByText('2 条来源关系')).toBeInTheDocument()
  expect(screen.getByText('doc-a#0')).toBeInTheDocument()
  expect(screen.getByText('doc-b#1')).toBeInTheDocument()
  expect(screen.getByText('doc-a::alpha → doc-a::beta')).toBeInTheDocument()
  expect(screen.getByText('doc-b::alpha → doc-b::beta')).toBeInTheDocument()
  expect(screen.getByText(/当前显示 2 \/ 共 3 条证据/)).toBeInTheDocument()
  expect(screen.getByText(/别名仅显示 2 \/ 3/)).toBeInTheDocument()
})

it('labels a defensive missing-evidence state instead of inventing provenance', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const data = subgraph(alpha)
  data.edges[0] = {
    ...data.edges[0],
    evidence: [],
    evidenceCount: 0,
    evidenceTruncated: false,
  }
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([community('community:v1:alpha', alpha)]),
  )
  mockedFetchCanonicalSubgraph.mockResolvedValue(data)

  render(<GraphView />)
  fireEvent.click(await screen.findByRole('button', { name: '选择规范实体 Alpha' }))

  expect(
    await screen.findByText('此聚合关系没有返回可展示的来源证据。'),
  ).toBeInTheDocument()
})

it('prevents a slower community response from overwriting the latest selection', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const beta = node('canonical:v1:beta', 'Beta')
  const gamma = node('canonical:v1:gamma', 'Gamma')
  const betaRequest = deferred<CanonicalSubgraph>()
  const gammaRequest = deferred<CanonicalSubgraph>()
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([
      community('community:v1:alpha', alpha),
      community('community:v1:beta', beta),
      community('community:v1:gamma', gamma),
    ]),
  )
  mockedFetchCanonicalSubgraph.mockImplementation((canonicalId) => {
    if (canonicalId === alpha.id) return Promise.resolve(subgraph(alpha))
    if (canonicalId === beta.id) return betaRequest.promise
    return gammaRequest.promise
  })

  render(<GraphView />)
  await screen.findAllByRole('button', { name: /Alpha/ })

  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Beta' }))
  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Gamma' }))
  gammaRequest.resolve(subgraph(gamma, node('canonical:v1:delta', 'Delta')))

  await waitFor(() =>
    expect(screen.getByRole('button', { name: '打开主题社区 Gamma' })).toHaveAttribute(
      'aria-pressed',
      'true',
    ),
  )

  betaRequest.resolve(subgraph(beta, node('canonical:v1:epsilon', 'Epsilon')))

  await waitFor(() =>
    expect(screen.getByRole('button', { name: '打开主题社区 Gamma' })).toHaveAttribute(
      'aria-pressed',
      'true',
    ),
  )
  expect(screen.queryByText('Epsilon')).not.toBeInTheDocument()
  expect(screen.getAllByText('Delta').length).toBeGreaterThan(0)
})

it('lets a subgraph request take over a pending refresh without leaving global loading stuck', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const beta = node('canonical:v1:beta', 'Beta')
  const currentOverview = overview([
    community('community:v1:alpha', alpha),
    community('community:v1:beta', beta),
  ])
  const pendingRefresh = deferred<CanonicalCommunityOverview>()
  mockedFetchCanonicalCommunities
    .mockResolvedValueOnce(currentOverview)
    .mockImplementationOnce(() => pendingRefresh.promise)
  mockedFetchCanonicalSubgraph.mockImplementation(async (canonicalId) =>
    canonicalId === alpha.id
      ? subgraph(alpha)
      : subgraph(beta, node('canonical:v1:delta', 'Delta')),
  )

  render(<GraphView />)
  await screen.findByRole('button', { name: '选择规范实体 Alpha' })

  fireEvent.click(screen.getByRole('button', { name: '刷新规范图' }))
  await waitFor(() => expect(mockedFetchCanonicalCommunities).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Beta' }))

  expect(await screen.findByRole('button', { name: '选择规范实体 Beta' })).toBeInTheDocument()
  expect(screen.queryByRole('status', { name: 'graph-loading' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '刷新规范图' })).toBeEnabled()

  pendingRefresh.resolve(currentOverview)
})

it('clears a failed refresh overlay when an existing community loads successfully', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const currentOverview = overview([community('community:v1:alpha', alpha)])
  mockedFetchCanonicalCommunities
    .mockResolvedValueOnce(currentOverview)
    .mockRejectedValueOnce(new ApiError('upstream', 'overview refresh failed'))
  mockedFetchCanonicalSubgraph.mockResolvedValue(subgraph(alpha))

  render(<GraphView />)
  await screen.findByRole('button', { name: '选择规范实体 Alpha' })

  fireEvent.click(screen.getByRole('button', { name: '刷新规范图' }))
  expect(await screen.findByRole('alert', { name: 'graph-error' })).toHaveTextContent(
    'overview refresh failed',
  )

  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Alpha' }))

  await waitFor(() =>
    expect(screen.queryByRole('alert', { name: 'graph-error' })).not.toBeInTheDocument(),
  )
  expect(screen.getByRole('button', { name: '选择规范实体 Alpha' })).toBeInTheDocument()
})

it('keeps the canonical overview truncation notice after a non-truncated subgraph loads', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  mockedFetchCanonicalCommunities.mockResolvedValue({
    ...overview([community('community:v1:alpha', alpha)]),
    metadata: {
      ...overview([]).metadata,
      communityCount: 1,
      nodeCount: 2,
      edgeCount: 1,
      evidenceCount: 1,
      truncated: true,
    },
  })
  mockedFetchCanonicalSubgraph.mockResolvedValue({
    ...subgraph(alpha),
    metadata: {
      ...subgraph(alpha).metadata,
      truncated: false,
    },
  })

  render(<GraphView />)

  expect(
    await screen.findByText('主题社区概览已达到返回上限，仅显示有界结果。'),
  ).toBeInTheDocument()
  expect(screen.queryByText('当前局部图已达到返回上限，仅显示有界结果。')).not.toBeInTheDocument()
})

it('clears stale node and relation detail after a successful graph replacement', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const gamma = node('canonical:v1:gamma', 'Gamma')
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([
      community('community:v1:alpha', alpha),
      community('community:v1:gamma', gamma),
    ]),
  )
  mockedFetchCanonicalSubgraph.mockImplementation(async (canonicalId) =>
    canonicalId === alpha.id
      ? subgraph(alpha)
      : subgraph(gamma, node('canonical:v1:delta', 'Delta')),
  )

  render(<GraphView />)

  fireEvent.click(await screen.findByRole('button', { name: '选择规范实体 Alpha' }))
  expect(await screen.findByText(alpha.id)).toBeInTheDocument()
  expect(screen.getByText('doc-a#0')).toBeInTheDocument()
  const relationButton = screen.getByRole('button', { name: '查看关系 uses 到 Beta' })
  fireEvent.click(relationButton)
  expect(relationButton).toHaveAttribute('aria-pressed', 'true')

  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Gamma' }))

  await waitFor(() => expect(screen.queryByText(alpha.id)).not.toBeInTheDocument())
  expect(screen.queryByText('doc-a#0')).not.toBeInTheDocument()
  expect(screen.getByText('选择一个规范实体')).toBeInTheDocument()
})

it('keeps the active graph identity when a new center is 404 and retries that failed target', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const gamma = node('canonical:v1:gamma', 'Gamma')
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([
      community('community:v1:alpha', alpha),
      community('community:v1:gamma', gamma),
    ]),
  )
  mockedFetchCanonicalSubgraph.mockImplementation(async (canonicalId) => {
    if (canonicalId === alpha.id) return subgraph(alpha)
    throw new ApiError('not_found', 'canonical center is outside the active scope')
  })

  render(<GraphView />)
  await screen.findByRole('button', { name: '选择规范实体 Alpha' })

  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Gamma' }))

  const error = await screen.findByRole('alert', { name: 'graph-subgraph-error' })
  expect(error).toHaveTextContent('canonical center is outside the active scope')
  expect(
    screen.getByRole('button', { name: '打开主题社区 Alpha' }),
  ).toHaveAttribute('aria-pressed', 'true')

  fireEvent.click(screen.getByRole('button', { name: '重试该局部图' }))
  await waitFor(() =>
    expect(mockedFetchCanonicalSubgraph).toHaveBeenLastCalledWith(gamma.id),
  )
})

it('keeps layout positions per community and uses preset positions for visibility toggles', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  const gamma = node('canonical:v1:gamma', 'Gamma')
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([
      community('community:v1:alpha', alpha),
      community('community:v1:gamma', gamma),
    ]),
  )
  mockedFetchCanonicalSubgraph.mockImplementation(async (canonicalId) =>
    canonicalId === alpha.id
      ? subgraph(alpha)
      : subgraph(gamma, node('canonical:v1:delta', 'Delta')),
  )

  render(<GraphView />)

  await waitFor(() => expect(cytoscapeLayouts.at(-1)).toBe('fcose'))
  fireEvent.click(screen.getByRole('checkbox', { name: /隐藏孤立节点/ }))
  await waitFor(() => expect(cytoscapeLayouts.at(-1)).toBe('preset'))

  fireEvent.click(screen.getByRole('button', { name: '打开主题社区 Gamma' }))
  await waitFor(() => expect(cytoscapeLayouts.at(-1)).toBe('fcose'))
})

it('labels search as current-subgraph only and preserves keyboard selection focus', async () => {
  const alpha = node('canonical:v1:alpha', 'Alpha')
  mockedFetchCanonicalCommunities.mockResolvedValue(
    overview([community('community:v1:alpha', alpha)]),
  )
  mockedFetchCanonicalSubgraph.mockResolvedValue(subgraph(alpha))

  render(<GraphView />)

  expect(await screen.findByLabelText('当前局部图搜索')).toBeInTheDocument()
  const alphaButton = await screen.findByRole('button', { name: '选择规范实体 Alpha' })
  fireEvent.click(alphaButton)

  expect(alphaButton).toHaveAttribute('aria-current', 'true')
  expect(document.activeElement).toBe(alphaButton)
})

it('keeps deterministic visual classes for canonical nodes and aggregate confidence', () => {
  expect(
    nodeVisualClasses(
      node('canonical:v1:alpha', 'Alpha', {
        entityType: 'Library',
        communityId: 'community:v1:one',
      }),
    ),
  ).toContain('type-library')
  expect(
    nodeVisualClasses(
      node('canonical:v1:alpha', 'Alpha', {
        entityType: 'Library',
        communityId: 'community:v1:one',
      }),
    ),
  ).toMatch(/community-palette-[0-3]/)
  expect(edgeConfidenceClass(0.9)).toBe('confidence-high')
  expect(edgeConfidenceClass(0.6)).toBe('confidence-medium')
  expect(edgeConfidenceClass(null)).toBe('confidence-unknown')
})
