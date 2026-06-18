// 引用：必须能回到来源 chunk（引用可追溯硬要求）。
export interface Citation {
  index: number // 答案中的角标号，从 1 开始
  chunkId: string // 来源 chunk 标识，用于反查原文
  documentName: string // 来源文档名
  location: string // 文档内位置（如页码 / 段落，形态待后端定）
  snippet: string // 原文片段
}

export interface Answer {
  id: string
  text: string // 答案正文
  confidence: 'high' | 'medium' | 'low' // 置信提示
  citations: Citation[]
}

// 对话消息：用户提问或 Agent 回答。
export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  text: string
  answer?: Answer // role === 'agent' 时携带结构化答案
}
