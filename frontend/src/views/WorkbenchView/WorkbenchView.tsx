import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch, ApiError } from '../../api/client'
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
} from '../../api/conversations'
import { ChatThread } from '../../components/ChatThread/ChatThread'
import { ChatComposer } from '../../components/ChatComposer/ChatComposer'
import { CitationPanel } from '../../components/CitationPanel/CitationPanel'
import { RunEventTimeline } from '../../components/RunEventTimeline/RunEventTimeline'
import { AgentRoom } from '../../components/AgentRoom/AgentRoom'
import { ConversationSidebar } from '../../components/ConversationSidebar/ConversationSidebar'
import { Panel } from '../../components/ui'
import { useRunEvents } from '../../hooks/useRunEvents'
import type {
  ChatMessage,
  ChatRequest,
  ChatRunCreated,
  Citation,
  Conversation,
  ConversationMessage,
} from '../../types'
import styles from './WorkbenchView.module.css'

export function WorkbenchView() {
  // 会话状态（多轮对话记忆核心）
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [convLoading, setConvLoading] = useState(true)
  const [messages, setMessages] = useState<ChatMessage[]>([])

  // 运行状态（SSE）
  const [chatRunId, setChatRunId] = useState<string | null>(null)
  const { events, currentStage, error } = useRunEvents(chatRunId)
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null)

  // 首次进入：加载会话列表（默认不自动选，空态引导「新建会话开始」）。
  const refreshList = useCallback(async () => {
    setConvLoading(true)
    try {
      const { items } = await listConversations()
      setConversations(items)
    } catch {
      // 拉取失败保持空列表，不抛错扰民（侧边栏会显示空态）
      setConversations([])
    } finally {
      setConvLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshList()
  }, [refreshList])

  // ConversationMessage → ChatMessage 转换（让历史回灌复用现有渲染/角标逻辑）。
  const toChatMessages = useCallback((list: ConversationMessage[]): ChatMessage[] => {
    return list.map((m) => ({
      id: m.messageId,
      role: m.role,
      text: m.text,
      // agent 消息还原结构化答案，user 消息不带 answer
      ...(m.role === 'agent' && m.confidence
        ? { answer: { text: m.text, confidence: m.confidence, citations: m.citations } }
        : {}),
    }))
  }, [])

  // 终态事件到达后，把答案/错误落成一条 agent 消息，并结束本次 Run 订阅。
  // 关键：只清 chatRunId 解除 busy，不清 conversationId（会话要保留供追问）。
  useEffect(() => {
    if (!chatRunId) return
    const last = events[events.length - 1]
    if (!last) return

    if (last.status === 'succeeded' && last.answer) {
      setMessages((prev) => [
        ...prev,
        { id: `a-${last.timestampMs}`, role: 'agent', text: last.answer!.text, answer: last.answer! },
      ])
      setChatRunId(null)
      // 终态后刷新侧边栏（messageCount/title 更新）
      void refreshList()
    } else if (last.status === 'failed') {
      setMessages((prev) => [
        ...prev,
        { id: `a-${last.timestampMs}`, role: 'agent', text: `回答失败：${last.message}` },
      ])
      setChatRunId(null)
    }
  }, [events, chatRunId, refreshList])

  // 新建会话：拿到 id → 设为当前 → 清空 messages → 侧边栏 unshift。
  async function handleCreate() {
    try {
      const detail = await createConversation()
      setConversationId(detail.conversationId)
      setMessages([])
      setConversations((prev) => [
        {
          conversationId: detail.conversationId,
          title: detail.title,
          createdAt: detail.createdAt,
          messageCount: detail.messageCount,
        },
        ...prev,
      ])
    } catch {
      // 新建失败静默（侧边栏列表不变）
    }
  }

  // 切换会话：拉历史 → 回灌 messages → 设 conversationId → 清 chatRunId。
  async function handleSelect(id: string) {
    if (id === conversationId) return
    try {
      const detail = await getConversation(id)
      setMessages(toChatMessages(detail.messages))
      setConversationId(detail.conversationId)
      setChatRunId(null)
      setActiveChunkId(null)
    } catch {
      // 切换失败静默
    }
  }

  // 删除会话：从列表移除；删的是当前会话则清空、回到空态。
  async function handleDelete(id: string) {
    try {
      await deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.conversationId !== id))
      if (id === conversationId) {
        setConversationId(null)
        setMessages([])
        setChatRunId(null)
      }
    } catch {
      // 删除失败静默
    }
  }

  // 提问：必须有当前 conversationId；POST /api/chat 带会话 id，响应的 conversationId 存住。
  async function handleSend(question: string) {
    if (!conversationId) return // 无会话不响应（侧边栏空态引导先新建）

    // 先把用户问题立即显示出来，再起 Run。
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', text: question },
    ])
    try {
      const body: ChatRequest = { question, conversationId }
      const { runId, conversationId: respConvId } = await apiFetch<ChatRunCreated>('/api/chat', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      // 首问时后端可能新建会话，以响应为准对齐
      if (respConvId && respConvId !== conversationId) {
        setConversationId(respConvId)
      }
      setChatRunId(runId)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '请求失败，请确认后端已启动'
      setMessages((prev) => [
        ...prev,
        { id: `a-${Date.now()}`, role: 'agent', text: `无法发起问答：${msg}` },
      ])
    }
  }

  // 引用面板展示最近一条 agent 回答的引用（而非历史全部），契合"当前回答"的语义。
  const citations: Citation[] = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg.role === 'agent' && msg.answer) return msg.answer.citations
    }
    return []
  }, [messages])

  return (
    <div className={styles.workbench}>
      <h1 className="sr-only">Archigraph · 档图知识工作台</h1>

      <ConversationSidebar
        conversations={conversations}
        currentId={conversationId}
        loading={convLoading}
        onSelect={handleSelect}
        onCreate={handleCreate}
        onDelete={handleDelete}
      />

      <section className={styles.mainCol}>
        <div className={styles.chatThread}>
          {conversationId ? (
            <ChatThread messages={messages} onCitationClick={setActiveChunkId} />
          ) : (
            <div className={styles.emptyState}>
              <p>选择左侧一个会话，或点「新建」开始一次对话。</p>
            </div>
          )}
        </div>
        <div className={styles.citation}>
          <CitationPanel citations={citations} activeChunkId={activeChunkId} />
        </div>
        <div className={styles.composer}>
          <ChatComposer onSend={handleSend} busy={chatRunId !== null || !conversationId} />
        </div>
      </section>

      <aside className={styles.sideCol}>
        <AgentRoom
          className={styles.stagePanel}
          stage={currentStage}
        />
        <Panel className={styles.timelinePanel} eyebrow="Run Events" title="运行轨迹">
          <RunEventTimeline events={events} />
          {error && <div className={styles.runError}>{error}</div>}
        </Panel>
      </aside>
    </div>
  )
}
