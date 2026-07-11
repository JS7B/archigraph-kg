export interface GraphNode {
  id: string
  label: string
  entityType: string // entity type (person, organization, concept, etc.)
  documentId?: string // source document identifier
  communityId?: string | null
  degree?: number // graph degree
  mentionCount?: number // mention count used for ranking
}

export interface GraphEdge {
  id: string
  source: string // source node id
  target: string // target node id
  relationType: string // business relation type
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
