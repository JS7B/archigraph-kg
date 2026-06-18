export interface GraphNode {
  id: string
  label: string
  entityType: string // 实体类型（人物/机构/技术概念等，开发期收敛）
}

export interface GraphEdge {
  id: string
  source: string // 源节点 id
  target: string // 目标节点 id
  relationType: string // 业务关系类型（先统一 :RELATES，类型作属性）
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}
