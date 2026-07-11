import { apiFetch } from './client'
import type {
  GraphCommunity,
  GraphData,
  GraphEdge,
  GraphNode,
  LocalSubgraph,
} from '../types'

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
  communityId?: string | null
  degree?: number // 后端 B4 提供；未就绪时字段缺失，前端 edges 兜底
  mentionCount?: number // 后端 B4 提供
}
interface RawEdge {
  source: string
  target: string
  type: string
  confidence?: number | null
  evidenceChunkId?: string | null
}
interface RawGraph {
  nodes: RawNode[]
  edges: RawEdge[]
}

function mapNode(n: RawNode): GraphNode {
  return {
    id: n.id,
    label: n.name,
    entityType: n.type,
    ...(typeof n.documentId === 'string' ? { documentId: n.documentId } : {}),
    ...(n.communityId !== undefined ? { communityId: n.communityId } : {}),
    // 后端字段可能未就绪：仅在存在时透传，缺省交给 View 层 edges 兜底
    ...(typeof n.degree === 'number' ? { degree: n.degree } : {}),
    ...(typeof n.mentionCount === 'number' ? { mentionCount: n.mentionCount } : {}),
  }
}

function mapEdge(e: RawEdge): GraphEdge {
  return {
    id: `${e.source}-${e.target}-${e.type}`,
    source: e.source,
    target: e.target,
    relationType: e.type,
    ...(e.confidence !== undefined ? { confidence: e.confidence } : {}),
    ...(e.evidenceChunkId !== undefined ? { evidenceChunkId: e.evidenceChunkId } : {}),
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

export interface CommunityQuery {
  limit?: number
  nodeLimit?: number
  documentId?: string
}

export interface SubgraphQuery {
  depth?: number
  limit?: number
  documentId?: string
  type?: string
  minConfidence?: number
}

function boundedInteger(value: number | undefined, fallback: number, max: number): number {
  if (value === undefined || !Number.isFinite(value)) return fallback
  return Math.min(max, Math.max(1, Math.floor(value)))
}

function appendOptionalParam(params: URLSearchParams, key: string, value: string | undefined) {
  if (value) params.set(key, value)
}

/** Fetch bounded connected-component summaries for the local-first graph view. */
export async function fetchCommunities(options: CommunityQuery = {}): Promise<GraphCommunity[]> {
  const params = new URLSearchParams({
    limit: String(boundedInteger(options.limit, 20, 100)),
    nodeLimit: String(boundedInteger(options.nodeLimit, 200, 500)),
  })
  appendOptionalParam(params, 'documentId', options.documentId)
  const raw = await apiFetch<RawCommunity[]>(`/api/graph/communities?${params.toString()}`)
  return raw.map(mapCommunity)
}

/** Fetch a bounded local subgraph around one center entity. */
export async function fetchSubgraph(
  entityId: string,
  options: SubgraphQuery = {},
): Promise<LocalSubgraph> {
  const params = new URLSearchParams({
    depth: String(boundedInteger(options.depth, 1, 4)),
    limit: String(boundedInteger(options.limit, 50, 100)),
  })
  appendOptionalParam(params, 'documentId', options.documentId)
  appendOptionalParam(params, 'type', options.type)
  if (options.minConfidence !== undefined && Number.isFinite(options.minConfidence)) {
    params.set('minConfidence', String(Math.min(1, Math.max(0, options.minConfidence))))
  }
  const raw = await apiFetch<RawSubgraph>(
    `/api/graph/entities/${encodeURIComponent(entityId)}/subgraph?${params.toString()}`,
  )
  return {
    centerId: raw.centerId,
    nodes: raw.nodes.map(mapNode),
    edges: raw.edges.map(mapEdge),
    metadata: raw.metadata,
  }
}

interface RawCommunity {
  id: string
  representativeNode: RawNode
  nodeCount: number
  edgeCount: number
  documentIds: string[]
}

interface RawSubgraph {
  centerId: string
  nodes: RawNode[]
  edges: RawEdge[]
  metadata: LocalSubgraph['metadata']
}

function mapCommunity(community: RawCommunity): GraphCommunity {
  return {
    id: community.id,
    representativeNode: mapNode(community.representativeNode),
    nodeCount: community.nodeCount,
    edgeCount: community.edgeCount,
    documentIds: community.documentIds,
  }
}
