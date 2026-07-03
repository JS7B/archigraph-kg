import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import type { ElementDefinition } from 'cytoscape'
import { Button, Card, Chip, DataValue, Eyebrow, Panel } from '../../components/ui'
import { ApiError } from '../../api/client'
import { fetchGraph } from '../../api/graph'
import type { GraphData, GraphEdge, GraphNode } from '../../types'
import styles from './GraphView.module.css'

interface NodeRelation {
  edge: GraphEdge
  otherNode: GraphNode
  direction: 'outgoing' | 'incoming'
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
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  // 拉取全图（套 LibraryView 的 refresh + useEffect 模式，补自建 loading flag）。
  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGraph()
      setGraphData(data)
      setLoadError(null)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '请求失败，请确认后端已启动'
      setLoadError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // Cytoscape elements 由 graphData 派生（数据到位才有图）。
  const graphElements: ElementDefinition[] = useMemo(() => {
    if (!graphData) return []
    return [
      ...graphData.nodes.map((node) => ({ data: { id: node.id, label: node.label } })),
      ...graphData.edges.map((edge) => ({
        data: { id: edge.id, source: edge.source, target: edge.target, label: edge.relationType },
      })),
    ]
  }, [graphData])

  const selectedRelations = useMemo(
    () => (selectedNode && graphData ? getNodeRelations(graphData, selectedNode.id) : []),
    [selectedNode, graphData],
  )

  // Cytoscape 实例：依赖 graphData，数据到位（或变化）后（重新）构建。
  useEffect(() => {
    if (!containerRef.current || !graphData) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: graphElements,
      style: cytoscapeStylesheet,
      layout: {
        name: 'cose',
        animate: false,
        fit: true,
        padding: 48,
        nodeRepulsion: 8000,
        idealEdgeLength: 110,
      },
      minZoom: 0.55,
      maxZoom: 2.2,
      wheelSensitivity: 0.15,
    })

    // 容器可能因视图常驻（hidden）而尺寸为 0，渲染后立即 resize + fit 兜底，
    // 避免图谱在可见时却显示空白。
    cy.resize()
    cy.fit(undefined, 48)

    cyRef.current = cy

    cy.on('tap', 'node', (event) => {
      const nodeId = event.target.id()
      setSelectedNode(findGraphNode(graphData, nodeId))
    })

    cy.on('tap', (event) => {
      if (event.target === cy) setSelectedNode(null)
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
    // graphElements 由 graphData 派生，依赖 graphData 即可覆盖数据变化重建。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData])

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
  }, [searchTerm])

  const isEmpty = !loading && !loadError && graphData && graphData.nodes.length === 0

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
        {loading && <div className={styles.statusMsg}>加载图谱中…</div>}
        {loadError && <div className={styles.statusMsg}>加载失败：{loadError}</div>}
        {isEmpty && (
          <div className={styles.statusMsg}>知识库还没有实体。上传文档并完成入库后，这里会显示实体与关系。</div>
        )}
        {/* 数据就绪才挂载 Cytoscape 容器，避免空容器闪烁 */}
        {!loading && !loadError && graphData && graphData.nodes.length > 0 && (
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
                        <span className={styles.relationTarget}>{otherNode.label}</span>
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
              {/* F5 无障碍：Cytoscape canvas 节点不可键盘访问，并行提供按钮列表作为可达路径。 */}
              {graphData && graphData.nodes.length > 0 ? (
                <ul className={styles.entityList} aria-label="实体列表">
                  {graphData.nodes.map((node) => (
                    <li key={node.id}>
                      <button
                        type="button"
                        className={styles.entityListBtn}
                        onClick={() => setSelectedNode(node)}
                      >
                        <span className={styles.entityListLabel}>{node.label}</span>
                        <Chip tone="accent">{node.entityType}</Chip>
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
