export type DocumentSourceType = 'pdf' | 'markdown' | 'txt' | 'repo'
export type ParseStatus = 'pending' | 'parsing' | 'parsed' | 'failed'
export type IndexStatus = 'pending' | 'indexing' | 'indexed' | 'failed'

export interface DocumentMeta {
  id: string
  name: string
  sourceType: DocumentSourceType
  parseStatus: ParseStatus
  indexStatus: IndexStatus
  chunkCount: number
}
