import type { Answer, ChatMessage } from '../../types'
import { Card, Chip, StatusBadge } from '../ui'
import styles from './ChatThread.module.css'

interface ChatThreadProps {
  messages: ChatMessage[]
  onCitationClick: (chunkId: string) => void
}

const confidenceStatus: Record<Answer['confidence'], 'success' | 'warning' | 'neutral'> = {
  high: 'success',
  medium: 'warning',
  low: 'neutral',
}

const confidenceLabel: Record<Answer['confidence'], string> = {
  high: '高置信',
  medium: '中置信',
  low: '低置信',
}

export function ChatThread({ messages, onCitationClick }: ChatThreadProps) {
  if (messages.length === 0) {
    return <div className={styles.empty}>提出第一个问题，开始与知识库对话</div>
  }

  return (
    <div className={styles.thread}>
      {messages.map((message) => {
        if (message.role === 'user') {
          return (
            <article key={message.id} className={`${styles.message} ${styles.user}`}>
              <div className={styles.meta}>你</div>
              <div className={`${styles.bubble} ${styles.userBubble}`}>{message.text}</div>
            </article>
          )
        }

        const answer = message.answer

        return (
          <article key={message.id} className={`${styles.message} ${styles.agent}`}>
            <div className={styles.meta}>GraphRAG Agent</div>
            <Card className={styles.agentCard} padding="md">
              <p className={styles.answerText}>
                {answer?.text ?? message.text}
                {answer?.citations.map((citation) => (
                  <button
                    key={`${message.id}-${citation.index}`}
                    className={styles.citationButton}
                    type="button"
                    onClick={() => onCitationClick(citation.chunkId)}
                    aria-label={`查看引用 ${citation.index}：${citation.documentId} ${citation.location}`}
                  >
                    [{citation.index}]
                  </button>
                ))}
              </p>
              {answer && (
                <footer className={styles.agentFooter}>
                  <StatusBadge status={confidenceStatus[answer.confidence]}>
                    {confidenceLabel[answer.confidence]}
                  </StatusBadge>
                  <Chip tone="accent">{answer.citations.length} 条可追溯引用</Chip>
                </footer>
              )}
            </Card>
          </article>
        )
      })}
    </div>
  )
}
