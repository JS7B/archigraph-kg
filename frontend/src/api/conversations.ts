import { apiFetch } from './client'
import type { Conversation, ConversationDetail } from '../types'

/**
 * 会话 CRUD API（多轮对话记忆）。
 *
 * 对应后端 /api/conversations/*（见 tasks/handoff-frontend-conversation-memory.md 冻结契约）。
 * 全走 apiFetch（带 X-API-Key 鉴权、统一错误结构）。
 *
 * MOCK 开关：后端会话 API 未就绪时设 USE_MOCK=true，用本地数据打通 UI 与状态流；
 * 后端就绪后改 false 切真实联调，删掉 mock 数据（见文件末尾）。
 */
const USE_MOCK = true // 后端会话 API 就绪后改 false 切真实联调，并删除文件末尾 mock 数据

export async function listConversations(): Promise<{ items: Conversation[] }> {
  if (USE_MOCK) return mockList()
  return apiFetch<{ items: Conversation[] }>('/api/conversations')
}

export async function createConversation(title?: string): Promise<ConversationDetail> {
  if (USE_MOCK) return mockCreate(title)
  return apiFetch<ConversationDetail>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify(title ? { title } : {}),
  })
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  if (USE_MOCK) return mockGet(id)
  return apiFetch<ConversationDetail>(`/api/conversations/${id}`)
}

export async function deleteConversation(id: string): Promise<void> {
  if (USE_MOCK) {
    mockDelete(id)
    return
  }
  // DELETE 后端返回 204（无 body）或 {deleted:true}；apiFetch 对 204 会 res.json() 失败，
  // 这里直接用 fetch + res.ok 判断，绕开 JSON 解析（参考清单 §四.2 说明）。
  const res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}/api/conversations/${id}`, {
    method: 'DELETE',
    headers: { 'X-API-Key': import.meta.env.VITE_API_KEY ?? '' },
  })
  if (!res.ok) throw new Error(`删除会话失败：${res.status}`)
}

/* ════════════════════ MOCK 数据（后端就绪后删除整段）════════════════════
   用途：后端会话 API 未就绪时，让前端 UI/状态管理流可独立打通。
   特征：内存态（刷新即丢），id 用 conv_mock{n}，消息含真实结构（含 citations 角标）。 */

const _mockCitations = [
  { index: 1, chunkId: 'mock-chunk-1', documentId: 'eval-planning.md', location: 'p.1', snippet: '知识图谱与向量检索是互补关系……' },
  { index: 2, chunkId: 'mock-chunk-2', documentId: 'eval-agents.md', location: '§3', snippet: 'Agent 的检索-生成编排……' },
]
const _mockStore: Map<string, ConversationDetail> = new Map([
  ['conv_mock1', {
    conversationId: 'conv_mock1', title: '知识图谱与向量检索的关系', createdAt: Date.now() - 3600_000, messageCount: 2,
    messages: [
      { messageId: 'conv_mock1#1', turnIndex: 1, role: 'user', text: '知识图谱和向量检索有什么关系？', confidence: null, citations: [] },
      { messageId: 'conv_mock1#2', turnIndex: 2, role: 'agent', text: '知识图谱与向量检索是互补关系：向量检索负责语义相似召回，知识图谱提供实体邻域与关系路径扩展，两者结合即 GraphRAG。[1][2]', confidence: 'high', citations: _mockCitations },
    ],
  }],
])

function mockList(): { items: Conversation[] } {
  return {
    items: [..._mockStore.values()]
      .map(({ messages, ...c }) => c)
      .sort((a, b) => b.createdAt - a.createdAt),
  }
}
function mockCreate(title?: string): ConversationDetail {
  const id = `conv_mock${_mockStore.size + 1}_${Date.now().toString(36)}`
  const detail: ConversationDetail = { conversationId: id, title: title ?? '新会话', createdAt: Date.now(), messageCount: 0, messages: [] }
  _mockStore.set(id, detail)
  return detail
}
function mockGet(id: string): ConversationDetail {
  return _mockStore.get(id) ?? mockCreate()
}
function mockDelete(id: string): void {
  _mockStore.delete(id)
}
