import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import type { ElementDefinition } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { Button, Card, Chip, DataValue, Eyebrow, Panel } from '../../components/ui'
import { ApiError } from '../../api/client'
import { fetchCommunities, fetchGraph, fetchSubgraph } from '../../api/graph'
import type { GraphCommunity, GraphData, GraphEdge, GraphNode } from '../../types'
import { edgeConfidenceClass, fallbackPosition, nodeVisualClasses } from './graphVisuals'
import styles from './GraphView.module.css'

// 注册 fcose 布局（大图布局质量明显优于内置 cose）。模块级注册一次即可。
cytoscape.use(fcose)

interface NodeRelation {
  edge: GraphEdge
  otherNode: GraphNode
  direction: 'outgoing' | 'incoming'
}

// 节点度数：后端 degree 字段优先，未就绪时用 edges 本地计数兜底。
// 这是「后端字段到位后一处切换」的唯一位置——?? 一旦拿到 degree 即自动改用。
function nodeDegree(node: GraphNode, edges: GraphEdge[]): number {
  if (typeof node.degree === 'number') return node.degree
  return edges.reduce(
    (count, edge) => count + (edge.source === node.id || edge.target === node.id ? 1 : 0),
    0,
  )
}

// 度数分档（3 可见档 + 孤立档，不做连续插值）：驱动节点尺寸与颜色深浅。
type DegreeTier = 'iso' | 'low' | 'mid' | 'hi'
function degreeTier(degree: number): DegreeTier {
  if (degree === 0) return 'iso'
  if (degree <= 2) return 'low'
  if (degree <= 5) return 'mid'
  return 'hi'
}

// 关系查找：接受 graphData 参数（替代旧的模块级 mockGraph 依赖）。
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

function edgeDocumentId(edge: GraphEdge, graph: GraphData): string | null {
  const source = findGraphNode(graph, edge.source)?.documentId
  const target = findGraphNode(graph, edge.target)?.documentId
  if (source) return source
  if (target) return target
  return edge.evidenceChunkId?.split('#')[0] || null
}

const cytoscapeStylesheet: NonNullable<cytoscape.CytoscapeOptions['style']> = [
  {
    selector: 'node',
    style: {
      // --color-accent: #6366f1; Cytoscape canvas styles cannot read CSS variables.
      'background-color': '#6366f1',
      // --color-on-accent: #ffffff.
      color: '#ffffff',
      label: 'data(label)',
      width: 58,
      height: 58,
      'border-width': 2,
      // --color-accent-border: #c7d2fe.
      'border-color': '#c7d2fe',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'font-size': 10,
      'font-weight': 'bold',
      'text-max-width': '90px',
      'text-wrap': 'wrap',
      'text-valign': 'center',
      'text-halign': 'center',
      'text-outline-width': 1,
      // --color-accent-active: #4338ca.
      'text-outline-color': '#4338ca',
      'overlay-opacity': 0,
    },
  },
  {
    selector: 'edge',
    style: {
      label: 'data(label)',
      width: 2,
      // --color-border-strong: #cbd5e1.
      'line-color': '#cbd5e1',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#cbd5e1',
      'curve-style': 'bezier',
      // --color-text-muted: #64748b.
      color: '#64748b',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'font-size': 9,
      'font-weight': 'bold',
      'text-background-color': '#ffffff', // --color-surface: #ffffff.
      'text-background-opacity': 0.9,
      'text-background-padding': '3px',
      'text-background-shape': 'roundrectangle',
      'text-rotation': 'autorotate',
      'overlay-opacity': 0,
    },
  },
  {
    selector: 'node.type-library',
    style: { 'background-color': '#0f766e' },
  },
  {
    selector: 'node.type-person',
    style: { 'background-color': '#b45309' },
  },
  {
    selector: 'node.type-organization',
    style: { 'background-color': '#0369a1' },
  },
  {
    selector: 'node.type-unknown',
    style: { 'background-color': '#64748b' },
  },
  {
    selector: 'node.community-local',
    style: { 'border-color': '#c7d2fe' },
  },
  {
    selector: 'node.community-unknown',
    style: { 'border-color': '#cbd5e1' },
  },
  {
    selector: 'node.community-palette-0',
    style: { 'border-color': '#c7d2fe' },
  },
  {
    selector: 'node.community-palette-1',
    style: { 'border-color': '#99f6e4' },
  },
  {
    selector: 'node.community-palette-2',
    style: { 'border-color': '#fed7aa' },
  },
  {
    selector: 'node.community-palette-3',
    style: { 'border-color': '#bae6fd' },
  },
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
  // 度数分档：孤立=灰小（噪声观感）→ 高度数=深大（核心突出）。颜色为靛紫由浅到深。
  {
    selector: 'node.deg-iso',
    style: {
      'background-color': '#cbd5e1', // --color-border-strong（灰，弱化噪声点）
      'border-color': '#e2e8f0',
      width: 34,
      height: 34,
      'font-size': 9,
    },
  },
  {
    selector: 'node.deg-low',
    style: {
      'background-color': '#a5b4fc', // 靛紫 300
      width: 46,
      height: 46,
    },
  },
  {
    selector: 'node.deg-mid',
    style: {
      'background-color': '#6366f1', // --color-accent
      width: 60,
      height: 60,
    },
  },
  {
    selector: 'node.deg-hi',
    style: {
      'background-color': '#4338ca', // --color-accent-active（最深，核心实体）
      'border-color': '#e0e7ff',
      width: 78,
      height: 78,
      'font-size': 12,
    },
  },
  {
    selector: 'node:selected',
    style: {
      // --color-accent-active: #4338ca.
      'background-color': '#4338ca',
      'border-width': 5,
      // --color-accent-softer: #e0e7ff.
      'border-color': '#e0e7ff',
    },
  },
  {
    selector: '.searchMatch',
    style: {
      // --color-accent-active: #4338ca.
      'background-color': '#4338ca',
      'border-width': 5,
      // --color-warning-soft: #fef3c7.
      'border-color': '#fef3c7',
    },
  },
  {
    selector: '.searchDimmed',
    style: {
      opacity: 0.22,
    },
  },
]

export function GraphView() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const layoutPositionsRef = useRef(new Map<string, { x: number; y: number }>())
  const entityButtonRefs = useRef(new Map<string, HTMLButtonElement>())
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [communities, setCommunities] = useState<GraphCommunity[]>([])
  const [selectedCommunity, setSelectedCommunity] = useState<GraphCommunity | null>(null)
  const [centerNodeId, setCenterNodeId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [subgraphLoading, setSubgraphLoading] = useState(false)
  const [subgraphError, setSubgraphError] = useState<string | null>(null)
  const [usingFallback, setUsingFallback] = useState(false)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  // 隐藏孤立节点（度数为 0），默认开：孤立点是噪声观感主源，一键切回全貌。不持久化。
  const [hideIsolated, setHideIsolated] = useState(true)

  const loadSubgraph = useCallback(
    async (nodeId: string, community: GraphCommunity | null = null) => {
      setSubgraphLoading(true)
      setSubgraphError(null)
      setCenterNodeId(nodeId)
      if (community) setSelectedCommunity(community)
      try {
        const data = await fetchSubgraph(nodeId)
        setGraphData(data)
        setSelectedNode(community ? null : findGraphNode(data, data.centerId))
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : '局部图加载失败，请稍后重试'
        setSubgraphError(msg)
      } finally {
        setSubgraphLoading(false)
      }
    },
    [setCenterNodeId, setGraphData, setSelectedCommunity, setSelectedNode, setSubgraphError, setSubgraphLoading],
  )

  // Prefer bounded community/local data, but retain the existing entities API as a fallback.
  const refresh = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    setSubgraphError(null)
    try {
      const available = await fetchCommunities()
      setCommunities(available)
      if (available.length > 0) {
        setUsingFallback(false)
        await loadSubgraph(available[0].representativeNode.id, available[0])
        return
      }
      setUsingFallback(true)
      setGraphData(await fetchGraph())
    } catch (err) {
      try {
        setUsingFallback(true)
        setGraphData(await fetchGraph())
      } catch (fallbackErr) {
        const source = fallbackErr instanceof ApiError ? fallbackErr : err
        const msg = source instanceof ApiError ? source.message : '请求失败，请确认后端已启动'
        setLoadError(msg)
      }
    } finally {
      setLoading(false)
    }
  }, [loadSubgraph])

  useEffect(() => {
    // The initial request drives the local-first loading lifecycle.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh()
  }, [refresh])

  // Cytoscape elements 由 graphData 派生：附度数分档 class；隐藏孤立时滤掉度数 0 的点
  // 及其悬挂边（两端都需可见）。
  const graphElements: ElementDefinition[] = useMemo(() => {
    if (!graphData) return []
    const withDegree = graphData.nodes.map((node) => ({
      node,
      degree: nodeDegree(node, graphData.edges),
    }))
    const visibleNodes = hideIsolated ? withDegree.filter(({ degree }) => degree > 0) : withDegree
    const visibleIds = new Set(visibleNodes.map(({ node }) => node.id))
    return [
      // eslint-disable-next-line react-hooks/refs
      ...visibleNodes.map(({ node, degree }, index) => ({
        data: { id: node.id, label: node.label, degree },
        position: layoutPositionsRef.current.get(node.id) ?? fallbackPosition(node.id, index),
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
          },
          classes: edgeConfidenceClass(edge.confidence),
        })),
    ]
  }, [graphData, hideIsolated, selectedCommunity])

  // 实体列表按度数降序（核心实体置顶）；带度数供列表展示。列表始终含全部节点
  // （键盘可达路径不因隐藏孤立点而丢失，孤立点自然沉到列表末尾）。
  const rankedNodes = useMemo(() => {
    if (!graphData) return []
    return graphData.nodes
      .map((node) => ({ node, degree: nodeDegree(node, graphData.edges) }))
      .sort((a, b) => b.degree - a.degree)
  }, [graphData])

  const selectedRelations = useMemo(
    () => (selectedNode && graphData ? getNodeRelations(graphData, selectedNode.id) : []),
    [selectedNode, graphData],
  )
  const selectedGraphData = graphData ?? { nodes: [], edges: [] }

  useEffect(() => {
    if (!selectedNode) return
    entityButtonRefs.current.get(selectedNode.id)?.focus()
  }, [selectedNode])

  // Cytoscape 实例：依赖 graphData，数据到位（或变化）后（重新）构建。
  useEffect(() => {
    if (!containerRef.current || !graphData) return

    const positions = layoutPositionsRef.current
    const hasStablePositions = positions.size > 0

    const cy = cytoscape({
      container: containerRef.current,
      elements: graphElements,
      style: cytoscapeStylesheet,
      layout: {
        name: 'fcose',
        quality: 'proof',
        animate: false,
        randomize: !hasStablePositions,
        fit: true,
        padding: 48,
        nodeSeparation: 120,
        idealEdgeLength: 110,
        nodeRepulsion: 8000,
      } as unknown as cytoscape.LayoutOptions,
      minZoom: 0.55,
      maxZoom: 2.2,
      wheelSensitivity: 0.15,
    })

    // 容器可能因视图常驻（hidden）而尺寸为 0，渲染后立即 resize + fit 兜底，
    // 避免图谱在可见时却显示空白。
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
      if (event.target === cy) setSelectedNode(null)
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
    // graphElements 由 graphData/hideIsolated 派生，二者变化即重建并重新布局。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData, hideIsolated])

  // 搜索高亮：仍在已渲染的 Cytoscape 实例上做前端 filter（体验好，不发请求）。
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
    // 依赖含 graphData/hideIsolated：cy 实例随二者重建后，本 effect 重跑复算高亮，
    // 否则切换「隐藏孤立节点」重建实例会丢掉搜索高亮（搜索框却仍有词）。
  }, [searchTerm, graphData, hideIsolated])

  const isEmpty = !loading && !loadError && graphData && graphData.nodes.length === 0

  // 当前画布可见节点数（隐藏孤立时 = 度数 > 0 的节点数）。用于"全被隐藏"的空态提示。
  const visibleNodeCount = useMemo(() => {
    if (!graphData) return 0
    if (!hideIsolated) return graphData.nodes.length
    return graphData.nodes.filter((node) => nodeDegree(node, graphData.edges) > 0).length
  }, [graphData, hideIsolated])

  // 有实体、但当前可见节点为 0（全孤立且开关开着）：画布会空白，需给出解释而非静默。
  const allHidden =
    !loading && !loadError && !!graphData && graphData.nodes.length > 0 && visibleNodeCount === 0

  return (
    <section className={styles.graphView}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <Eyebrow>Knowledge Graph</Eyebrow>
          <h1 className={styles.title}>图谱探索</h1>
          <p className={styles.subtitle}>
            从知识库的实体与关系中探索，点击节点查看详情，输入名称高亮匹配。
          </p>
        </div>
      </header>

      <div className={styles.canvasShell} aria-label="知识图谱画布">
        {loading && (
          <div
            className={styles.statusMsg}
            role="status"
            aria-label={subgraphLoading ? 'graph-subgraph-loading' : 'graph-loading'}
          >
            {subgraphLoading ? '加载局部图中…' : '加载图谱中…'}
          </div>
        )}
        {!loading && subgraphLoading && (
          <div className={styles.statusMsg} role="status" aria-label="graph-subgraph-loading">
            加载局部图中…
          </div>
        )}
        {loadError && <div className={styles.statusMsg} role="status" aria-label="graph-error">加载失败：{loadError}</div>}
        {subgraphError && (
          <div className={styles.statusMsg} role="status" aria-label="graph-subgraph-error">
            局部图加载失败：{subgraphError}
          </div>
        )}
        {isEmpty && (
          <div className={styles.statusMsg} role="status" aria-label="graph-empty">
            知识库还没有实体。上传文档并完成入库后，这里会显示实体与关系。
          </div>
        )}
        {/* 全部实体都是孤立点、被默认隐藏：画布会空白，给出提示而非静默空白 */}
        {allHidden && (
          <div className={styles.statusMsg}>
            {graphData!.nodes.length} 个实体当前都是孤立点（无关系连边），已按「隐藏孤立节点」默认隐藏。
            关闭右侧开关可查看全部。
          </div>
        )}
        {/* 数据就绪且有可见节点才挂载 Cytoscape 容器，避免空容器闪烁 */}
        {!loading && !loadError && visibleNodeCount > 0 && (
          <>
            <div ref={containerRef} className={styles.canvas} />
            <div className={styles.canvasNote}>拖拽移动画布，滚轮缩放，点击节点查看详情。</div>
          </>
        )}
      </div>

      {/* 右侧边栏：实体搜索 + 实体详情垂直一列，跨两行贴顶 */}
      <aside className={styles.sidebar}>
        <Card className={styles.searchCard} padding="md">
          <div className={styles.searchRow}>
            <label className={styles.searchLabel}>
              <span className={styles.searchCaption}>实体搜索</span>
              <input
                className={styles.searchInput}
                type="search"
                inputMode="search"
                enterKeyHint="search"
                value={searchTerm}
                placeholder="搜索实体…"
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </label>
            {/* 刷新是低频次要操作，用 ghost 避免与搜索主任务抢视觉焦点 */}
            <Button
              variant="ghost"
              disabled={loading}
              onClick={() => void refresh()}
              aria-label="刷新图谱"
            >
              刷新图谱
            </Button>
          </div>
          <span className={styles.searchHint}>输入名称会高亮匹配节点，并弱化其他图谱元素。</span>
          {communities.length > 0 && (
            <div aria-label="communities">
              <span className={styles.searchCaption}>社区</span>
              <ul className={styles.entityList}>
                {communities.map((community) => (
                  <li key={community.id}>
                    <button
                      type="button"
                      className={styles.entityListBtn}
                      aria-pressed={selectedCommunity?.id === community.id}
                      aria-current={centerNodeId === community.representativeNode.id ? 'true' : undefined}
                      onClick={() => void loadSubgraph(community.representativeNode.id, community)}
                    >
                      <span className={styles.entityListLabel}>{community.representativeNode.label}</span>
                      <span className={styles.entityListMeta}>
                        <Chip tone="accent">{community.nodeCount} nodes</Chip>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {usingFallback && <span className={styles.searchHint}>社区接口暂不可用，已显示实体列表。</span>}
          {rankedNodes.length > 0 && (
            <div aria-label="entities">
              <span className={styles.searchCaption}>Entities</span>
              <ul className={styles.entityList}>
                {rankedNodes.map(({ node, degree }) => (
                  <li key={node.id}>
                    <button
                      type="button"
                      className={styles.entityListBtn}
                      ref={(element) => {
                        if (element) entityButtonRefs.current.set(node.id, element)
                        else entityButtonRefs.current.delete(node.id)
                      }}
                      aria-current={selectedNode?.id === node.id ? 'true' : undefined}
                      onClick={() => setSelectedNode(node)}
                    >
                      <span className={styles.entityListLabel}>{node.label}</span>
                      <span className={styles.entityListMeta}>
                        <Chip tone="accent">{node.entityType}</Chip>
                        <span className={styles.entityDegree}>{degree}</span>
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
            <span className={styles.toggleText}>隐藏孤立节点（度数为 0 的噪声实体）</span>
          </label>
        </Card>

        <Panel className={styles.detailPanel} eyebrow="Entity Detail" title="实体详情">
          {selectedNode ? (
            <div className={styles.detailBody}>
              <div className={styles.entityHeader}>
                <div className={styles.entityTitleRow}>
                  <h2 className={styles.entityTitle}>{selectedNode.label}</h2>
                  <Chip tone="accent">{selectedNode.entityType}</Chip>
                </div>
                <DataValue label="entity id">{selectedNode.id}</DataValue>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={subgraphLoading}
                  onClick={() => void loadSubgraph(selectedNode.id)}
                >
                  {subgraphLoading ? '加载局部图中…' : '展开局部图'}
                </Button>
              </div>

              <section className={styles.detailBody} aria-label="实体关系">
                <h3 className={styles.sectionTitle}>关联关系</h3>
                {selectedRelations.length > 0 ? (
                  <ul className={styles.relationList}>
                    {selectedRelations.map(({ edge, otherNode, direction }) => (
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
                          aria-pressed={selectedEdge?.id === edge.id}
                          onClick={() => setSelectedEdge(edge)}
                        >
                          <span className={styles.relationTarget}>{otherNode.label}</span>
                        </button>
                        <div className={styles.evidenceDetail} aria-label="relation evidence">
                          <DataValue label="confidence">
                            {typeof edge.confidence === 'number' ? edge.confidence.toFixed(2) : 'Unknown'}
                          </DataValue>
                          <DataValue label="evidence chunk">
                            {edge.evidenceChunkId ?? <span className={styles.missingEvidence}>Missing evidence</span>}
                          </DataValue>
                          <DataValue label="document">
                            {edgeDocumentId(edge, selectedGraphData) ?? <span className={styles.missingEvidence}>Missing document</span>}
                          </DataValue>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.noRelations}>这个实体当前没有关系。</p>
                )}
              </section>
            </div>
          ) : (
            <div className={styles.emptyState}>
              <h2 className={styles.emptyTitle}>实体列表</h2>
              <p className={styles.emptyCopy}>
                点击图中节点，或用下方列表选择实体查看详情（可键盘 Tab/方向键访问）。
              </p>
              {/* F5 无障碍：Cytoscape canvas 节点不可键盘访问，并行提供按钮列表作为可达路径。
                  F2：按度数降序，每项带类型 Chip 与度数。 */}
              {rankedNodes.length > 0 ? (
                <ul className={styles.entityList} aria-label="实体列表">
                  {rankedNodes.map(({ node, degree }) => (
                    <li key={node.id}>
                      <button
                        type="button"
                        className={styles.entityListBtn}
                        onClick={() => setSelectedNode(node)}
                      >
                        <span className={styles.entityListLabel}>{node.label}</span>
                        <span className={styles.entityListMeta}>
                          <Chip tone="accent">{node.entityType}</Chip>
                          <span className={styles.entityDegree} title="图内度数">
                            {degree}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={styles.noRelations}>知识库暂无实体。</p>
              )}
            </div>
          )}
        </Panel>
      </aside>
    </section>
  )
}
