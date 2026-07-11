export interface GraphNode {
  id: string
  label: string
  entityType: string // 实体类型（人物/机构/技术概念等，开发期收敛）
  documentId?: string
  degree?: number // 图内度数（后端 B4 提供；缺省时前端用 edges 本地计数兜底）
  mentionCount?: number // 提及次数（后端 B4 提供，用于展示层排序/分级参考）
}

export interface GraphEdge {
  id: string
  source: string // 源节点 id
  target: string // 目标节点 id
  relationType: string // 业务关系类型（先统一 :RELATES，类型作属性）
  confidence?: number | null
  evidenceChunkId?: string | null
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphCommunity {
  id: string
  representativeNode: GraphNode
  nodeCount: number
  edgeCount: number
  documentIds: string[]
}

export interface LocalSubgraphMetadata {
  depth: number
  limit: number
  nodeCount: number
  edgeCount: number
  truncated: boolean
}

export interface LocalSubgraph extends GraphData {
  centerId: string
  metadata: LocalSubgraphMetadata
}
