import { apiFetch } from './client'
import type {
  CanonicalCommunityOverview,
  CanonicalSubgraph,
  GraphCommunity,
  GraphData,
  GraphEdge,
  GraphEvidence,
  GraphNode,
  LocalSubgraph,
  ProjectionCoverage,
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

export interface CanonicalCommunityQuery {
  limit?: number
  nodeLimit?: number
  edgeLimit?: number
  evidenceLimit?: number
  documentId?: string
  minConfidence?: number
}

export interface CanonicalSubgraphQuery {
  depth?: number
  nodeLimit?: number
  edgeLimit?: number
  evidenceLimit?: number
  documentId?: string
  minConfidence?: number
}

export interface CanonicalSearchQuery {
  limit?: number
  documentId?: string
}

function boundedInteger(value: number | undefined, fallback: number, max: number): number {
  if (value === undefined || !Number.isFinite(value)) return fallback
  return Math.min(max, Math.max(1, Math.floor(value)))
}

function appendOptionalParam(params: URLSearchParams, key: string, value: string | undefined) {
  if (value) params.set(key, value)
}

function appendConfidence(
  params: URLSearchParams,
  value: number | undefined,
) {
  if (value !== undefined && Number.isFinite(value)) {
    params.set('minConfidence', String(Math.min(1, Math.max(0, value))))
  }
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

interface RawCanonicalNode {
  id: string
  name: string
  type: string
  identity: 'canonical'
  documentIds: string[]
  sourceEntityCount: number
  mentionCount: number
  aliases: string[]
  aliasCount: number
  aliasesTruncated: boolean
  degree: number
  communityId?: string | null
}

interface RawCanonicalEvidence {
  chunkId: string
  documentId: string
  sourceEntityId: string
  targetEntityId: string
  confidence: number | null
}

interface RawCanonicalEdge {
  id: string
  source: string
  target: string
  type: string
  confidence: number | null
  supportCount: number
  evidenceCount: number
  evidence: RawCanonicalEvidence[]
  evidenceTruncated: boolean
}

interface RawCanonicalCommunity {
  id: string
  representativeNode: RawCanonicalNode
  nodeCount: number
  edgeCount: number
  totalSupport: number
  documentIds: string[]
}

interface RawCanonicalCommunityOverview {
  communities: RawCanonicalCommunity[]
  coverage: ProjectionCoverage
  metadata: CanonicalCommunityOverview['metadata']
}

interface RawCanonicalSubgraph {
  centerId: string
  nodes: RawCanonicalNode[]
  edges: RawCanonicalEdge[]
  coverage: ProjectionCoverage
  metadata: CanonicalSubgraph['metadata']
}

function mapCanonicalNode(node: RawCanonicalNode): GraphNode {
  return {
    id: node.id,
    label: node.name,
    entityType: node.type,
    identity: node.identity,
    documentIds: node.documentIds,
    sourceEntityCount: node.sourceEntityCount,
    mentionCount: node.mentionCount,
    aliases: node.aliases,
    aliasCount: node.aliasCount,
    aliasesTruncated: node.aliasesTruncated,
    degree: node.degree,
    ...(node.communityId !== undefined ? { communityId: node.communityId } : {}),
  }
}

function mapCanonicalEvidence(evidence: RawCanonicalEvidence): GraphEvidence {
  return { ...evidence }
}

function mapCanonicalEdge(edge: RawCanonicalEdge): GraphEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    relationType: edge.type,
    confidence: edge.confidence,
    supportCount: edge.supportCount,
    evidenceCount: edge.evidenceCount,
    evidence: edge.evidence.map(mapCanonicalEvidence),
    evidenceTruncated: edge.evidenceTruncated,
  }
}

/** Fetch deterministic topic communities from the accepted canonical projection. */
export async function fetchCanonicalCommunities(
  options: CanonicalCommunityQuery = {},
): Promise<CanonicalCommunityOverview> {
  const params = new URLSearchParams({
    limit: String(boundedInteger(options.limit, 20, 100)),
    nodeLimit: String(boundedInteger(options.nodeLimit, 200, 500)),
    edgeLimit: String(boundedInteger(options.edgeLimit, 400, 1000)),
    evidenceLimit: String(boundedInteger(options.evidenceLimit, 20, 20)),
  })
  appendOptionalParam(params, 'documentId', options.documentId)
  appendConfidence(params, options.minConfidence)
  const raw = await apiFetch<RawCanonicalCommunityOverview>(
    `/api/graph/canonical/communities?${params.toString()}`,
  )
  return {
    communities: raw.communities.map((item) => ({
      id: item.id,
      representativeNode: mapCanonicalNode(item.representativeNode),
      nodeCount: item.nodeCount,
      edgeCount: item.edgeCount,
      totalSupport: item.totalSupport,
      documentIds: item.documentIds,
    })),
    coverage: raw.coverage,
    metadata: raw.metadata,
  }
}

/** Fetch one bounded canonical graph around a canonical center identity. */
export async function fetchCanonicalSubgraph(
  canonicalId: string,
  options: CanonicalSubgraphQuery = {},
): Promise<CanonicalSubgraph> {
  const params = new URLSearchParams({
    depth: String(boundedInteger(options.depth, 1, 4)),
    nodeLimit: String(boundedInteger(options.nodeLimit, 50, 100)),
    edgeLimit: String(boundedInteger(options.edgeLimit, 100, 200)),
    evidenceLimit: String(boundedInteger(options.evidenceLimit, 20, 20)),
  })
  appendOptionalParam(params, 'documentId', options.documentId)
  appendConfidence(params, options.minConfidence)
  const raw = await apiFetch<RawCanonicalSubgraph>(
    `/api/graph/canonical/entities/${encodeURIComponent(canonicalId)}/subgraph?${params.toString()}`,
  )
  return {
    centerId: raw.centerId,
    nodes: raw.nodes.map(mapCanonicalNode),
    edges: raw.edges.map(mapCanonicalEdge),
    coverage: raw.coverage,
    metadata: raw.metadata,
  }
}

/** Search canonical names and accepted source aliases in the active evidence scope. */
export async function searchCanonicalEntities(
  query: string,
  options: CanonicalSearchQuery = {},
): Promise<GraphNode[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(boundedInteger(options.limit, 20, 100)),
  })
  appendOptionalParam(params, 'documentId', options.documentId)
  const raw = await apiFetch<RawCanonicalNode[]>(
    `/api/graph/canonical/search?${params.toString()}`,
  )
  return raw.map(mapCanonicalNode)
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
