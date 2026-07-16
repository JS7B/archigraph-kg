export interface GraphNode {
  id: string
  label: string
  entityType: string // entity type (person, organization, concept, etc.)
  identity?: 'source' | 'canonical'
  documentId?: string // source document identifier
  documentIds?: string[] // sorted supporting documents for a canonical identity
  sourceEntityCount?: number
  aliases?: string[]
  aliasCount?: number
  aliasesTruncated?: boolean
  communityId?: string | null
  degree?: number // graph degree
  mentionCount?: number // mention count used for ranking
}

export interface GraphEvidence {
  chunkId: string
  documentId: string
  sourceEntityId: string
  targetEntityId: string
  confidence: number | null
}

export interface GraphEdge {
  id: string
  source: string // source node id
  target: string // target node id
  relationType: string // business relation type
  confidence?: number | null
  evidenceChunkId?: string | null
  supportCount?: number
  evidenceCount?: number
  evidence?: GraphEvidence[]
  evidenceTruncated?: boolean
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
  totalSupport?: number
  documentIds: string[]
}

export interface ProjectionCoverage {
  sourceEntityCount: number
  acceptedSourceEntityCount: number
  reviewSourceEntityCount: number
  unresolvedSourceEntityCount: number
  sourceRelationCount: number
  projectedSourceRelationCount: number
  excludedRelationCount: number
  collapsedSelfRelationCount: number
}

export interface CanonicalCommunityMetadata {
  limit: number
  nodeLimit: number
  edgeLimit: number
  evidenceLimit: number
  communityCount: number
  nodeCount: number
  edgeCount: number
  evidenceCount: number
  truncated: boolean
}

export interface CanonicalCommunityOverview {
  communities: GraphCommunity[]
  coverage: ProjectionCoverage
  metadata: CanonicalCommunityMetadata
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

export interface CanonicalSubgraphMetadata {
  depth: number
  nodeLimit: number
  edgeLimit: number
  evidenceLimit: number
  nodeCount: number
  edgeCount: number
  evidenceCount: number
  truncated: boolean
}

export interface CanonicalSubgraph extends GraphData {
  centerId: string
  coverage: ProjectionCoverage
  metadata: CanonicalSubgraphMetadata
}
