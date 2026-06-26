import { useEffect, useMemo, useState } from 'react'
import { apiFetch, ApiError } from '../../api/client'
import { ChatThread } from '../../components/ChatThread/ChatThread'
import { ChatComposer } from '../../components/ChatComposer/ChatComposer'
import { CitationPanel } from '../../components/CitationPanel/CitationPanel'
import { RunEventTimeline } from '../../components/RunEventTimeline/RunEventTimeline'
import { AgentRoom } from '../../components/AgentRoom/AgentRoom'
import { Panel } from '../../components/ui'
import { useRunEvents } from '../../hooks/useRunEvents'
import type { ChatMessage, Citation } from '../../types'
import styles from './WorkbenchView.module.css'

interface ChatRunCreated {
  runId: string
}

export function WorkbenchView() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatRunId, setChatRunId] = useState<string | null>(null)
  const { events, currentStage, error } = useRunEvents(chatRunId)
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null)

  // 终态事件到达后，把答案/错误落成一条 agent 消息，并结束本次 Run 订阅。
  useEffect(() => {
    if (!chatRunId) return
    const last = events[events.length - 1]
    if (!last) return

    if (last.status === 'succeeded' && last.answer) {
      setMessages((prev) => [
        ...prev,
        { id: `a-${last.timestamp_ms}`, role: 'agent', text: last.answer!.text, answer: last.answer! },
      ])
      setChatRunId(null)
    } else if (last.status === 'failed') {
      setMessages((prev) => [
        ...prev,
        { id: `a-${last.timestamp_ms}`, role: 'agent', text: `回答失败：${last.message}` },
      ])
      setChatRunId(null)
    }
  }, [events, chatRunId])

  async function handleSend(question: string) {
    // 先把用户问题立即显示出来，再起 Run；失败时补一条错误消息。
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', text: question },
    ])
    try {
      const { runId } = await apiFetch<ChatRunCreated>('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ question }),
      })
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
      <section className={styles.mainCol}>
        <div className={styles.chatThread}>
          <ChatThread messages={messages} onCitationClick={setActiveChunkId} />
        </div>
        <div className={styles.citation}>
          <CitationPanel citations={citations} activeChunkId={activeChunkId} />
        </div>
        <div className={styles.composer}>
          <ChatComposer onSend={handleSend} />
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
