import type { Citation } from './answer'

// 多轮对话记忆：会话与会话消息类型（对齐后端 conversation API 的 camelCase 输出）。

/** 会话列表条目（GET /api/conversations 的 items 元素）。 */
export interface Conversation {
  conversationId: string
  title: string
  createdAt: number // 毫秒时间戳
  messageCount: number
}

/** 对话消息（图谱 Message 的前端形态；GET /api/conversations/{id}.messages 元素）。 */
export interface ConversationMessage {
  messageId: string // 形如 "conv_aaaa#1"
  turnIndex: number // 从 1 起
  role: 'user' | 'agent'
  text: string
  confidence: 'high' | 'medium' | 'low' | null // agent 消息；user 为 null
  citations: Citation[] // agent 消息同 chat answer.citations；user 为 []
}

/** 单会话详情（GET /api/conversations/{id}、POST /api/conversations 响应）。 */
export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[]
}

// 请求体：POST /api/chat 带 conversationId（首问 null/不传，追问回传）。
export interface ChatRequest {
  question: string
  conversationId?: string | null
}

// 响应体：POST /api/chat。
export interface ChatRunCreated {
  runId: string
  conversationId: string // 始终返回；首问时后端新建会话
}
