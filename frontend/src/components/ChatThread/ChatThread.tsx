import type { ChatMessage } from '../../types'

interface ChatThreadProps {
  messages: ChatMessage[]
  onCitationClick: (chunkId: string) => void
}

// 占位：渲染消息列表；答案的引用角标点击回调已接通（引用可追溯硬要求）。
export function ChatThread({ messages, onCitationClick }: ChatThreadProps) {
  if (messages.length === 0) {
    return <div>提出第一个问题，开始与知识库对话（占位）</div>
  }
  return (
    <div>
      {messages.map((m) => (
        <div key={m.id}>
          <strong>{m.role === 'user' ? '你' : 'Agent'}：</strong>
          {m.text}
          {m.answer?.citations.map((c) => (
            <sup
              key={c.index}
              style={{ cursor: 'pointer', color: 'var(--color-accent)' }}
              onClick={() => onCitationClick(c.chunkId)}
            >
              [{c.index}]
            </sup>
          ))}
        </div>
      ))}
    </div>
  )
}
