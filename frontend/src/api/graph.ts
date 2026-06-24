import { apiFetch } from './client'
import type { GraphData, GraphEdge, GraphNode } from '../types'

/**
 * 图谱 API 领域层：后端调用 + 字段映射收口。
 *
 * 后端（routers/graph.py）返回的字段名与前端 types/graph.ts 不一致，
 * 全部映射收口在这里，View 层只认 GraphData / GraphNode / GraphEdge。
 *
 * 字段映射：
 * - node: 后端 {id, name, type, documentId} → 前端 {id, label:name, entityType:type}
 * - edge: 后端 {source, target, type, confidence} → 前端 {id:生成, source, target, relationType:type}
 *   （后端 edge 无 id，前端需 id 给 React key / Cytoscape element，用 source-target-type 生成）
 */

// 后端原始响应结构（仅本文件内部用，不导出）
interface RawNode {
  id: string
  name: string
  type: string
  documentId: string
}
interface RawEdge {
  source: string
  target: string
  type: string
  confidence?: number | null
}
interface RawGraph {
  nodes: RawNode[]
  edges: RawEdge[]
}

function mapNode(n: RawNode): GraphNode {
  return { id: n.id, label: n.name, entityType: n.type }
}

function mapEdge(e: RawEdge): GraphEdge {
  return {
    id: `${e.source}-${e.target}-${e.type}`,
    source: e.source,
    target: e.target,
    relationType: e.type,
  }
}

function mapGraph(raw: RawGraph): GraphData {
  return { nodes: raw.nodes.map(mapNode), edges: raw.edges.map(mapEdge) }
}

/** 加载全图：GET /api/graph/entities?limit=100 → {nodes,edges} */
export async function fetchGraph(limit = 100): Promise<GraphData> {
  const raw = await apiFetch<RawGraph>(`/api/graph/entities?limit=${limit}`)
  return mapGraph(raw)
}

/** 实体 1 跳邻域：GET /api/graph/entities/{id}/neighbors → {nodes,edges}（含中心） */
export async function fetchNeighbors(entityId: string): Promise<GraphData> {
  const raw = await apiFetch<RawGraph>(
    `/api/graph/entities/${encodeURIComponent(entityId)}/neighbors`,
  )
  return mapGraph(raw)
}

/** 实体名称模糊搜索：GET /api/graph/search?q=&limit=20 → [node]（只返点不返边） */
export async function searchEntities(q: string, limit = 20): Promise<GraphNode[]> {
  const raw = await apiFetch<RawNode[]>(
    `/api/graph/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  )
  return raw.map(mapNode)
}
