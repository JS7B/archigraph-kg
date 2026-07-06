import { apiFetch } from './client'
import type { Conversation, ConversationDetail } from '../types'

/**
 * 会话 CRUD API（多轮对话记忆）。
 *
 * 对应后端 /api/conversations/*（见 tasks/handoff-frontend-conversation-memory.md 冻结契约）。
 * 全走 apiFetch（带 X-API-Key 鉴权、统一错误结构）。后端会话 API 已就绪，直连真实。
 */

export async function listConversations(): Promise<{ items: Conversation[] }> {
  return apiFetch<{ items: Conversation[] }>('/api/conversations')
}

export async function createConversation(title?: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify(title ? { title } : {}),
  })
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/conversations/${id}`)
}

export async function renameConversation(id: string, title: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/api/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export async function deleteConversation(id: string): Promise<void> {
  // DELETE 后端返回 {deleted:true}（清单 §2.2，会话删除较轻走同步）。
  // 用 fetch + res.ok 判断，避免 apiFetch 对可能无 body 的 204 做 res.json() 失败；
  // 同时补 X-API-Key 鉴权头（与 apiFetch 一致）。
  const res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}/api/conversations/${id}`, {
    method: 'DELETE',
    headers: { 'X-API-Key': import.meta.env.VITE_API_KEY ?? '' },
  })
  if (!res.ok) {
    // 尝试解析后端统一错误结构（404 等），失败则给状态码兜底
    let detail = `删除会话失败：${res.status}`
    try {
      const body = await res.json()
      if (body?.error?.message) detail = body.error.message
    } catch {
      /* 无 body 忽略 */
    }
    throw new Error(detail)
  }
}
