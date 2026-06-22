// 引用：必须能回到来源 chunk（引用可追溯硬要求）。
// 字段对齐后端 qa.models.Citation 的 camelCase 输出。
export interface Citation {
  index: number // 答案中的角标号，从 1 开始
  chunkId: string // 来源 chunk 标识，用于反查原文
  documentId: string // 来源文档标识（后端 document_id 即源文件名，可兼作显示名）
  location: string // 文档内位置（页码 / 标题路径 / 字符区间，后端拼成可读串）
  snippet: string // 原文片段
}

// 对齐后端 qa.models.Answer 的 camelCase 输出：text + confidence + citations。
export interface Answer {
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
