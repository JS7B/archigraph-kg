import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import type { ElementDefinition } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { ApiError } from '../../api/client'
import {
  fetchCanonicalCommunities,
  fetchCanonicalSubgraph,
} from '../../api/graph'
import { Button, Card, Chip, DataValue, Eyebrow, Panel } from '../../components/ui'
import type {
  CanonicalCommunityMetadata,
  CanonicalSubgraphMetadata,
  GraphCommunity,
  GraphData,
  GraphEdge,
  GraphNode,
  ProjectionCoverage,
} from '../../types'
import { edgeConfidenceClass, fallbackPosition, nodeVisualClasses } from './graphVisuals'
import styles from './GraphView.module.css'

cytoscape.use(fcose)

interface NodeRelation {
  edge: GraphEdge
  otherNode: GraphNode
  direction: 'outgoing' | 'incoming'
}

type Position = { x: number; y: number }

function nodeDegree(node: GraphNode, edges: GraphEdge[]): number {
  if (typeof node.degree === 'number') return node.degree
  return edges.reduce(
    (count, edge) => count + (edge.source === node.id || edge.target === node.id ? 1 : 0),
    0,
  )
}

type DegreeTier = 'iso' | 'low' | 'mid' | 'hi'

function degreeTier(degree: number): DegreeTier {
  if (degree === 0) return 'iso'
  if (degree <= 2) return 'low'
  if (degree <= 5) return 'mid'
  return 'hi'
}

function findGraphNode(graph: GraphData, nodeId: string): GraphNode | null {
  return graph.nodes.find((node) => node.id === nodeId) ?? null
}

function getNodeRelations(graph: GraphData, nodeId: string): NodeRelation[] {
  return graph.edges.reduce<NodeRelation[]>((relations, edge) => {
    if (edge.source === nodeId) {
      const otherNode = findGraphNode(graph, edge.target)
      if (otherNode) relations.push({ edge, otherNode, direction: 'outgoing' })
    }
    if (edge.target === nodeId) {
      const otherNode = findGraphNode(graph, edge.source)
      if (otherNode) relations.push({ edge, otherNode, direction: 'incoming' })
    }
    return relations
  }, [])
}

function requestMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

function communityScope(community: GraphCommunity | null, centerId: string): string {
  return `canonical:${community?.id ?? `center:${centerId}`}`
}

const cytoscapeStylesheet: NonNullable<cytoscape.CytoscapeOptions['style']> = [
  {
    selector: 'node',
    style: {
      'background-color': '#6366f1',
      color: '#ffffff',
      label: 'data(label)',
      width: 58,
      height: 58,
      'border-width': 2,
      'border-color': '#c7d2fe',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'font-size': 10,
      'font-weight': 'bold',
      'text-max-width': '90px',
      'text-wrap': 'wrap',
      'text-valign': 'center',
      'text-halign': 'center',
      'text-outline-width': 1,
      'text-outline-color': '#4338ca',
      'overlay-opacity': 0,
    },
  },
  {
    selector: 'edge',
    style: {
      label: 'data(label)',
      width: 2,
      'line-color': '#cbd5e1',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#cbd5e1',
      'curve-style': 'bezier',
      color: '#64748b',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'font-size': 9,
      'font-weight': 'bold',
      'text-background-color': '#ffffff',
      'text-background-opacity': 0.9,
      'text-background-padding': '3px',
      'text-background-shape': 'roundrectangle',
      'text-rotation': 'autorotate',
      'overlay-opacity': 0,
    },
  },
  { selector: 'node.type-library', style: { 'background-color': '#0f766e' } },
  { selector: 'node.type-person', style: { 'background-color': '#b45309' } },
  { selector: 'node.type-organization', style: { 'background-color': '#0369a1' } },
  { selector: 'node.type-unknown', style: { 'background-color': '#64748b' } },
  { selector: 'node.community-palette-0', style: { 'border-color': '#c7d2fe' } },
  { selector: 'node.community-palette-1', style: { 'border-color': '#99f6e4' } },
  { selector: 'node.community-palette-2', style: { 'border-color': '#fed7aa' } },
  { selector: 'node.community-palette-3', style: { 'border-color': '#bae6fd' } },
  {
    selector: 'edge.confidence-high',
    style: { width: 3, 'line-color': '#16a34a', 'target-arrow-color': '#16a34a' },
  },
  {
    selector: 'edge.confidence-medium',
    style: { width: 2, 'line-color': '#d97706', 'target-arrow-color': '#d97706' },
  },
  {
    selector: 'edge.confidence-low',
    style: {
      width: 1,
      'line-color': '#94a3b8',
      'target-arrow-color': '#94a3b8',
      'line-style': 'dashed',
    },
  },
  {
    selector: 'edge.confidence-unknown',
    style: { width: 1, 'line-color': '#cbd5e1', 'target-arrow-color': '#cbd5e1' },
  },
  {
    selector: 'node.deg-iso',
    style: {
      'background-color': '#cbd5e1',
      'border-color': '#e2e8f0',
      width: 34,
      height: 34,
      'font-size': 9,
    },
  },
  {
    selector: 'node.deg-low',
    style: { 'background-color': '#a5b4fc', width: 46, height: 46 },
  },
  {
    selector: 'node.deg-mid',
    style: { 'background-color': '#6366f1', width: 60, height: 60 },
  },
  {
    selector: 'node.deg-hi',
    style: {
      'background-color': '#4338ca',
      'border-color': '#e0e7ff',
      width: 78,
      height: 78,
      'font-size': 12,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'background-color': '#4338ca',
      'border-width': 5,
      'border-color': '#e0e7ff',
    },
  },
  {
    selector: '.searchMatch',
    style: {
      'background-color': '#4338ca',
      'border-width': 5,
      'border-color': '#fef3c7',
    },
  },
  { selector: '.searchDimmed', style: { opacity: 0.22 } },
]

export function GraphView() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const requestGenerationRef = useRef(0)
  const positionsByScopeRef = useRef(new Map<string, Map<string, Position>>())
  const entityButtonRefs = useRef(new Map<string, HTMLButtonElement>())
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [communities, setCommunities] = useState<GraphCommunity[]>([])
  const [coverage, setCoverage] = useState<ProjectionCoverage | null>(null)
  const [communityMetadata, setCommunityMetadata] =
    useState<CanonicalCommunityMetadata | null>(null)
  const [graphMetadata, setGraphMetadata] = useState<CanonicalSubgraphMetadata | null>(null)
  const [selectedCommunity, setSelectedCommunity] = useState<GraphCommunity | null>(null)
  const [centerNodeId, setCenterNodeId] = useState<string | null>(null)
  const [layoutScopeKey, setLayoutScopeKey] = useState('canonical:empty')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [subgraphLoading, setSubgraphLoading] = useState(false)
  const [subgraphError, setSubgraphError] = useState<string | null>(null)
  const [failedSubgraphRequest, setFailedSubgraphRequest] = useState<{
    nodeId: string
    community: GraphCommunity | null
  } | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [hideIsolated, setHideIsolated] = useState(true)

  const applyGraphReplacement = useCallback(
    (data: GraphData & {
      centerId: string
      coverage: ProjectionCoverage
      metadata: CanonicalSubgraphMetadata
    }, community: GraphCommunity | null) => {
      setGraphData({ nodes: data.nodes, edges: data.edges })
      setCoverage(data.coverage)
      setGraphMetadata(data.metadata)
      setCenterNodeId(data.centerId)
      setSelectedCommunity(community)
      setLayoutScopeKey(communityScope(community, data.centerId))
      setSelectedNode(null)
      setSelectedEdge(null)
      setSearchTerm('')
      setFailedSubgraphRequest(null)
    },
    [
      setCenterNodeId,
      setCoverage,
      setFailedSubgraphRequest,
      setGraphData,
      setGraphMetadata,
      setLayoutScopeKey,
      setSearchTerm,
      setSelectedCommunity,
      setSelectedEdge,
      setSelectedNode,
    ],
  )

  const loadSubgraph = useCallback(
    async (nodeId: string, community: GraphCommunity | null) => {
      const generation = ++requestGenerationRef.current
      // A local graph request supersedes any pending/failed overview refresh.
      // The older refresh sees a stale generation and cannot write its finally state.
      setLoading(false)
      setLoadError(null)
      setSubgraphLoading(true)
      setSubgraphError(null)
      setFailedSubgraphRequest(null)
      try {
        const data = await fetchCanonicalSubgraph(nodeId)
        if (generation !== requestGenerationRef.current) return
        applyGraphReplacement(data, community)
      } catch (error) {
        if (generation !== requestGenerationRef.current) return
        setSubgraphError(requestMessage(error, '规范局部图加载失败，请稍后重试'))
        setFailedSubgraphRequest({ nodeId, community })
      } finally {
        if (generation === requestGenerationRef.current) setSubgraphLoading(false)
      }
    },
    [
      applyGraphReplacement,
      setFailedSubgraphRequest,
      setLoadError,
      setLoading,
      setSubgraphError,
      setSubgraphLoading,
    ],
  )

  const refresh = useCallback(async () => {
    const generation = ++requestGenerationRef.current
    setLoading(true)
    setLoadError(null)
    setSubgraphError(null)
    setFailedSubgraphRequest(null)
    setSubgraphLoading(false)
    try {
      const overview = await fetchCanonicalCommunities()
      if (generation !== requestGenerationRef.current) return
      setCommunities(overview.communities)
      setCoverage(overview.coverage)
      setCommunityMetadata(overview.metadata)
      if (overview.communities.length === 0) {
        setGraphData({ nodes: [], edges: [] })
        setGraphMetadata(null)
        setSelectedCommunity(null)
        setCenterNodeId(null)
        setSelectedNode(null)
        setSelectedEdge(null)
        setSearchTerm('')
        setLayoutScopeKey('canonical:empty')
        return
      }

      const firstCommunity = overview.communities[0]
      setSubgraphLoading(true)
      const data = await fetchCanonicalSubgraph(firstCommunity.representativeNode.id)
      if (generation !== requestGenerationRef.current) return
      applyGraphReplacement(data, firstCommunity)
    } catch (error) {
      if (generation !== requestGenerationRef.current) return
      setLoadError(requestMessage(error, '规范图请求失败，请确认后端已启动'))
    } finally {
      if (generation === requestGenerationRef.current) {
        setLoading(false)
        setSubgraphLoading(false)
      }
    }
  }, [
    applyGraphReplacement,
    setCenterNodeId,
    setCommunities,
    setCommunityMetadata,
    setCoverage,
    setFailedSubgraphRequest,
    setGraphData,
    setGraphMetadata,
    setLayoutScopeKey,
    setLoadError,
    setLoading,
    setSearchTerm,
    setSelectedCommunity,
    setSelectedEdge,
    setSelectedNode,
    setSubgraphError,
    setSubgraphLoading,
  ])

  useEffect(() => {
    // The initial canonical request owns the graph loading lifecycle.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh()
    return () => {
      requestGenerationRef.current += 1
    }
  }, [refresh])

  const graphElements: ElementDefinition[] = useMemo(() => {
    if (!graphData) return []
    const withDegree = graphData.nodes.map((node) => ({
      node,
      degree: nodeDegree(node, graphData.edges),
    }))
    const visibleNodes = hideIsolated ? withDegree.filter(({ degree }) => degree > 0) : withDegree
    const visibleIds = new Set(visibleNodes.map(({ node }) => node.id))
    // Reading saved positions during render is intentional: they are immutable
    // for this render and are written only by the Cytoscape lifecycle below.
    // eslint-disable-next-line react-hooks/refs
    const savedPositions = positionsByScopeRef.current.get(layoutScopeKey)
    return [
      ...visibleNodes.map(({ node, degree }, index) => ({
        data: { id: node.id, label: node.label, degree },
        position: savedPositions?.get(node.id) ?? fallbackPosition(node.id, index),
        classes: `deg-${degreeTier(degree)} ${nodeVisualClasses(node, selectedCommunity?.id)}`,
      })),
      ...graphData.edges
        .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
        .map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.relationType,
            confidence: edge.confidence,
            supportCount: edge.supportCount,
          },
          classes: edgeConfidenceClass(edge.confidence),
        })),
    ]
  }, [graphData, hideIsolated, layoutScopeKey, selectedCommunity])

  const rankedNodes = useMemo(() => {
    if (!graphData) return []
    return graphData.nodes
      .map((node) => ({ node, degree: nodeDegree(node, graphData.edges) }))
      .sort(
        (left, right) =>
          right.degree - left.degree ||
          (right.node.sourceEntityCount ?? 0) - (left.node.sourceEntityCount ?? 0) ||
          left.node.id.localeCompare(right.node.id),
      )
  }, [graphData])

  const selectedRelations = useMemo(
    () => (selectedNode && graphData ? getNodeRelations(graphData, selectedNode.id) : []),
    [selectedNode, graphData],
  )

  useEffect(() => {
    if (!selectedNode) return
    entityButtonRefs.current.get(selectedNode.id)?.focus()
  }, [selectedNode])

  useEffect(() => {
    if (!containerRef.current || !graphData || graphElements.length === 0) return

    let positions = positionsByScopeRef.current.get(layoutScopeKey)
    if (!positions) {
      positions = new Map<string, Position>()
      positionsByScopeRef.current.set(layoutScopeKey, positions)
    }
    const hasStablePositions = positions.size > 0
    const cy = cytoscape({
      container: containerRef.current,
      elements: graphElements,
      style: cytoscapeStylesheet,
      layout: hasStablePositions
        ? {
            name: 'preset',
            fit: true,
            padding: 48,
          }
        : ({
            name: 'fcose',
            quality: 'proof',
            animate: false,
            randomize: true,
            fit: true,
            padding: 48,
            nodeSeparation: 120,
            idealEdgeLength: 110,
            nodeRepulsion: 8000,
          } as unknown as cytoscape.LayoutOptions),
      minZoom: 0.55,
      maxZoom: 2.2,
      wheelSensitivity: 0.15,
    })

    cy.resize()
    cy.fit(undefined, 48)
    cyRef.current = cy

    cy.nodes().forEach((node) => {
      const position = node.position()
      if (Number.isFinite(position.x) && Number.isFinite(position.y)) {
        positions.set(node.id(), position)
      }
    })

    cy.on('tap', 'node', (event) => {
      const nodeId = event.target.id()
      setSelectedNode(findGraphNode(graphData, nodeId))
      setSelectedEdge(null)
    })
    cy.on('tap', 'edge', (event) => {
      const edgeId = event.target.id()
      const edge = graphData.edges.find((candidate) => candidate.id === edgeId) ?? null
      setSelectedEdge(edge)
      if (edge) setSelectedNode(findGraphNode(graphData, edge.source))
    })
    cy.on('tap', (event) => {
      if (event.target === cy) {
        setSelectedNode(null)
        setSelectedEdge(null)
      }
    })

    return () => {
      cy.nodes().forEach((node) => {
        const position = node.position()
        if (Number.isFinite(position.x) && Number.isFinite(position.y)) {
          positions.set(node.id(), position)
        }
      })
      cy.destroy()
      cyRef.current = null
    }
  }, [graphData, graphElements, layoutScopeKey])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    const normalizedSearch = searchTerm.trim().toLocaleLowerCase()
    const nodes = cy.nodes()
    const edges = cy.edges()
    nodes.removeClass('searchMatch searchDimmed')
    edges.removeClass('searchDimmed')
    if (!normalizedSearch) return

    const matchingNodes = nodes.filter((node) => {
      const label = String(node.data('label') ?? '').toLocaleLowerCase()
      return label.includes(normalizedSearch)
    })
    nodes.not(matchingNodes).addClass('searchDimmed')
    edges.addClass('searchDimmed')
    matchingNodes.addClass('searchMatch')
    matchingNodes.connectedEdges().removeClass('searchDimmed')
  }, [searchTerm, graphData, hideIsolated, layoutScopeKey])

  const visibleNodeCount = useMemo(() => {
    if (!graphData) return 0
    if (!hideIsolated) return graphData.nodes.length
    return graphData.nodes.filter((node) => nodeDegree(node, graphData.edges) > 0).length
  }, [graphData, hideIsolated])

  const isEmpty =
    !loading && !loadError && !!graphData && graphData.nodes.length === 0
  const allHidden =
    !loading &&
    !loadError &&
    !!graphData &&
    graphData.nodes.length > 0 &&
    visibleNodeCount === 0
  const isBusy = loading || subgraphLoading

  return (
    <section className={styles.graphView}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <Eyebrow>Canonical Knowledge Graph</Eyebrow>
          <h1 className={styles.title}>规范图谱探索</h1>
          <p className={styles.subtitle}>
            相同知识在不同文档中的来源实体会汇聚为规范实体；关系仍保留每条来源证据。
          </p>
        </div>
      </header>

      <div className={styles.canvasShell} aria-label="规范知识图谱画布">
        {loading && !loadError && (
          <div
            className={styles.statusMsg}
            role="status"
            aria-label={subgraphLoading ? 'graph-subgraph-loading' : 'graph-loading'}
          >
            {subgraphLoading ? '正在加载规范局部图…' : '正在加载规范图…'}
          </div>
        )}
        {!loading && subgraphLoading && (
          <div className={styles.statusMsg} role="status" aria-label="graph-subgraph-loading">
            正在加载规范局部图…
          </div>
        )}
        {loadError && (
          <div className={styles.statusMsg} role="alert" aria-label="graph-error">
            <div className={styles.statusPanel}>
              <span>规范图加载失败：{loadError}</span>
              <Button size="sm" variant="ghost" onClick={() => void refresh()}>
                重试加载规范图
              </Button>
            </div>
          </div>
        )}
        {subgraphError && (
          <div className={styles.statusMsg} role="alert" aria-label="graph-subgraph-error">
            <div className={styles.statusPanel}>
              <span>规范局部图加载失败：{subgraphError}</span>
              {failedSubgraphRequest && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    void loadSubgraph(
                      failedSubgraphRequest.nodeId,
                      failedSubgraphRequest.community,
                    )
                  }
                >
                  重试该局部图
                </Button>
              )}
            </div>
          </div>
        )}
        {isEmpty && (
          <div className={styles.statusMsg} role="status" aria-label="graph-empty">
            {coverage && coverage.acceptedSourceEntityCount > 0
              ? '规范图目前没有可展示的关系社区；孤立规范实体不进入默认社区。'
              : '还没有可展示的规范实体。完成文档入库与实体解析后，这里会出现主题社区。'}
          </div>
        )}
        {allHidden && (
          <div className={styles.statusMsg}>
            当前局部图的节点都是孤立节点。关闭右侧“隐藏孤立节点”可查看。
          </div>
        )}
        {!loading && !loadError && visibleNodeCount > 0 && (
          <>
            <div ref={containerRef} className={styles.canvas} />
            <div className={styles.canvasNote}>
              拖拽移动画布，滚轮缩放，点击节点查看规范身份与来源。
            </div>
          </>
        )}
      </div>

      <aside className={styles.sidebar}>
        <Card className={styles.searchCard} padding="md">
          <div className={styles.searchRow}>
            <label className={styles.searchLabel}>
              <span className={styles.searchCaption}>当前局部图搜索</span>
              <input
                aria-label="当前局部图搜索"
                className={styles.searchInput}
                type="search"
                inputMode="search"
                enterKeyHint="search"
                value={searchTerm}
                placeholder="高亮当前图中的实体…"
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </label>
            <Button
              variant="ghost"
              disabled={isBusy}
              onClick={() => void refresh()}
              aria-label="刷新规范图"
            >
              刷新
            </Button>
          </div>
          <span className={styles.searchHint}>
            此搜索只高亮当前局部图，不会在后台切换社区。
          </span>

          {coverage && (
            <div className={styles.coverageNotice} aria-label="规范投影覆盖情况">
              <span>{coverage.acceptedSourceEntityCount} 个来源实体已解析</span>
              <span>{coverage.reviewSourceEntityCount} 个待审核实体未进入规范图</span>
              {coverage.unresolvedSourceEntityCount > 0 && (
                <span>{coverage.unresolvedSourceEntityCount} 个来源实体尚未解析</span>
              )}
              <span>
                {coverage.projectedSourceRelationCount} / {coverage.sourceRelationCount}{' '}
                条来源关系进入当前投影
              </span>
            </div>
          )}
          {graphMetadata?.truncated && (
            <p className={styles.boundsNotice}>
              当前局部图已达到返回上限，仅显示有界结果。
            </p>
          )}
          {communityMetadata?.truncated && (
            <p className={styles.boundsNotice}>
              主题社区概览已达到返回上限，仅显示有界结果。
            </p>
          )}

          {communities.length > 0 && (
            <div aria-label="主题社区">
              <span className={styles.searchCaption}>主题社区</span>
              <ul className={styles.entityList}>
                {communities.map((community) => (
                  <li key={community.id}>
                    <button
                      type="button"
                      className={styles.entityListBtn}
                      aria-label={`打开主题社区 ${community.representativeNode.label}`}
                      aria-pressed={selectedCommunity?.id === community.id}
                      aria-current={
                        centerNodeId === community.representativeNode.id ? 'true' : undefined
                      }
                      onClick={() =>
                        void loadSubgraph(community.representativeNode.id, community)
                      }
                    >
                      <span className={styles.entityListLabel}>
                        {community.representativeNode.label}
                      </span>
                      <span className={styles.entityListMeta}>
                        <Chip tone="accent">{community.nodeCount} 节点</Chip>
                        <span className={styles.entityDegree} title="聚合关系数">
                          {community.edgeCount}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {rankedNodes.length > 0 && (
            <div aria-label="规范实体列表">
              <span className={styles.searchCaption}>当前规范实体</span>
              <ul className={styles.entityList}>
                {rankedNodes.map(({ node, degree }) => (
                  <li key={node.id}>
                    <button
                      type="button"
                      className={styles.entityListBtn}
                      aria-label={`选择规范实体 ${node.label}`}
                      ref={(element) => {
                        if (element) entityButtonRefs.current.set(node.id, element)
                        else entityButtonRefs.current.delete(node.id)
                      }}
                      aria-current={selectedNode?.id === node.id ? 'true' : undefined}
                      onClick={() => {
                        setSelectedNode(node)
                        setSelectedEdge(null)
                      }}
                    >
                      <span className={styles.entityListLabel}>{node.label}</span>
                      <span className={styles.entityListMeta}>
                        <Chip tone="accent">{node.entityType}</Chip>
                        <span className={styles.entityDegree} title="投影度数">
                          {degree}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <label className={styles.toggleRow}>
            <input
              type="checkbox"
              className={styles.toggleInput}
              checked={hideIsolated}
              onChange={(event) => setHideIsolated(event.target.checked)}
            />
            <span className={styles.toggleText}>隐藏孤立节点</span>
          </label>
        </Card>

        <Panel className={styles.detailPanel} eyebrow="Canonical Detail" title="规范实体详情">
          {selectedNode ? (
            <div className={styles.detailBody}>
              <div className={styles.entityHeader}>
                <div className={styles.entityTitleRow}>
                  <h2 className={styles.entityTitle}>{selectedNode.label}</h2>
                  <Chip tone="accent">规范 · {selectedNode.entityType}</Chip>
                </div>
                <DataValue label="canonical id">{selectedNode.id}</DataValue>
                <div className={styles.entityStats}>
                  <DataValue label="来源文档">
                    {(selectedNode.documentIds ?? []).join('、') || '无'}
                  </DataValue>
                  <DataValue label="来源实体">
                    {selectedNode.sourceEntityCount ?? 0}
                  </DataValue>
                  <DataValue label="mentions">{selectedNode.mentionCount ?? 0}</DataValue>
                </div>
                <div className={styles.aliasBlock}>
                  <span className={styles.searchCaption}>名称与别名</span>
                  <span>{(selectedNode.aliases ?? []).join(' · ') || '无别名'}</span>
                  {selectedNode.aliasesTruncated && (
                    <span className={styles.boundsNotice}>
                      别名仅显示 {(selectedNode.aliases ?? []).length} /{' '}
                      {selectedNode.aliasCount ?? 0}
                    </span>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={subgraphLoading}
                  onClick={() => void loadSubgraph(selectedNode.id, selectedCommunity)}
                >
                  {subgraphLoading ? '正在加载局部图…' : '以此实体为中心'}
                </Button>
              </div>

              <section className={styles.detailBody} aria-label="规范实体关系">
                <h3 className={styles.sectionTitle}>聚合关系与来源证据</h3>
                {selectedRelations.length > 0 ? (
                  <ul className={styles.relationList}>
                    {selectedRelations.map(({ edge, otherNode, direction }) => {
                      const evidence = edge.evidence ?? []
                      const evidenceCount = edge.evidenceCount ?? evidence.length
                      const supportCount = edge.supportCount ?? 1
                      return (
                        <li key={edge.id} className={styles.relationItem}>
                          <div className={styles.relationTopline}>
                            <span className={styles.relationType}>{edge.relationType}</span>
                            <span className={styles.relationDirection}>
                              {direction === 'outgoing' ? 'out' : 'in'}
                            </span>
                          </div>
                          <button
                            type="button"
                            className={styles.relationTargetButton}
                            aria-label={`查看关系 ${edge.relationType} 到 ${otherNode.label}`}
                            aria-pressed={selectedEdge?.id === edge.id}
                            onClick={() => setSelectedEdge(edge)}
                          >
                            <span className={styles.relationTarget}>{otherNode.label}</span>
                          </button>
                          <div className={styles.relationSummary}>
                            <Chip tone="accent">{supportCount} 条来源关系</Chip>
                            <DataValue label="最高置信度">
                              {typeof edge.confidence === 'number'
                                ? edge.confidence.toFixed(2)
                                : '未知'}
                            </DataValue>
                          </div>

                          {evidence.length > 0 ? (
                            <ul className={styles.evidenceList} aria-label="关系来源证据">
                              {evidence.map((item) => (
                                <li
                                  className={styles.evidenceItem}
                                  key={[
                                    item.documentId,
                                    item.chunkId,
                                    item.sourceEntityId,
                                    item.targetEntityId,
                                  ].join('|')}
                                >
                                  <div className={styles.evidenceDetail}>
                                    <DataValue label="document">{item.documentId}</DataValue>
                                    <DataValue label="chunk">{item.chunkId}</DataValue>
                                    <DataValue label="confidence">
                                      {typeof item.confidence === 'number'
                                        ? item.confidence.toFixed(2)
                                        : '未知'}
                                    </DataValue>
                                  </div>
                                  <span className={styles.evidenceEndpoints}>
                                    {item.sourceEntityId} → {item.targetEntityId}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className={styles.missingEvidence}>
                              此聚合关系没有返回可展示的来源证据。
                            </p>
                          )}
                          {edge.evidenceTruncated && (
                            <p className={styles.boundsNotice}>
                              当前显示 {evidence.length} / 共 {evidenceCount} 条证据
                            </p>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <p className={styles.noRelations}>这个规范实体在当前局部图中没有关系。</p>
                )}
              </section>
            </div>
          ) : (
            <div className={styles.emptyState}>
              <h2 className={styles.emptyTitle}>选择一个规范实体</h2>
              <p className={styles.emptyCopy}>
                可点击画布节点，或使用上方键盘可达的规范实体列表查看跨文档来源与关系证据。
              </p>
            </div>
          )}
        </Panel>
      </aside>
    </section>
  )
}
