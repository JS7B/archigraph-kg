import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { Answer, ChatMessage, Citation } from '../../types'
import { Card, StatusBadge } from '../ui'
import { remarkCitations } from './remarkCitations'
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

// 内联引用芯片：正文角标与末尾汇总行复用同一造型与点击回调
// （点击 → CitationPanel 高亮对应证据 + 滚动定位）。
function CitationChip({ index, onClick }: { index: number; onClick: () => void }) {
  return (
    <button
      type="button"
      className={styles.citationButton}
      onClick={onClick}
      aria-label={`查看引用 ${index}`}
    >
      [{index}]
    </button>
  )
}

// 按当前回答的 citations 生成 markdown 组件覆写：
// - #cite-n 链接（由 remarkCitations 插件产出）→ 内联引用芯片（n 超范围则降级为纯文本 [n]）
// - 其余链接照常渲染，新窗口打开
function buildMarkdownComponents(
  citations: Citation[],
  onCitationClick: (chunkId: string) => void,
): Components {
  const byIndex = new Map(citations.map((c) => [c.index, c]))
  return {
    a({ href, children, ...props }) {
      const matched = href?.match(/^#cite-(\d+)$/)
      if (matched) {
        const index = Number(matched[1])
        const citation = byIndex.get(index)
        if (citation) {
          return <CitationChip index={index} onClick={() => onCitationClick(citation.chunkId)} />
        }
        return <>[{index}]</>
      }
      return (
        <a href={href} target="_blank" rel="noreferrer" {...props}>
          {children}
        </a>
      )
    },
  }
}

const REMARK_PLUGINS = [remarkGfm, remarkCitations]

// 单条消息抽成 memo 子组件：onCitationClick 稳定（useState setter）、message 引用稳定，
// 故点角标只更新 activeChunkId 时，各条消息 props 未变 → 跳过重渲染，不重解析 Markdown。
const MessageItem = memo(function MessageItem({
  message,
  onCitationClick,
}: {
  message: ChatMessage
  onCitationClick: (chunkId: string) => void
}) {
  const answer = message.answer
  const citations = useMemo(() => answer?.citations ?? [], [answer])
  const components = useMemo(
    () => buildMarkdownComponents(citations, onCitationClick),
    [citations, onCitationClick],
  )

  if (message.role === 'user') {
    return (
      <article className={`${styles.message} ${styles.user}`}>
        <div className={styles.meta}>你</div>
        <div className={`${styles.bubble} ${styles.userBubble}`}>{message.text}</div>
      </article>
    )
  }

  const bodyText = answer?.text ?? message.text

  return (
    <article className={`${styles.message} ${styles.agent}`}>
      <div className={styles.meta}>Archigraph Agent</div>
      <Card className={styles.agentCard} padding="md">
        <div className={styles.answerText}>
          <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={components}>
            {bodyText}
          </ReactMarkdown>
        </div>
        {answer && (
          <footer className={styles.agentFooter}>
            <StatusBadge status={confidenceStatus[answer.confidence]}>
              {confidenceLabel[answer.confidence]}
            </StatusBadge>
            {citations.length > 0 && (
              <div className={styles.citationSummary}>
                <span className={styles.citationSummaryLabel}>本回答引用：</span>
                {citations.map((citation) => (
                  <CitationChip
                    key={citation.index}
                    index={citation.index}
                    onClick={() => onCitationClick(citation.chunkId)}
                  />
                ))}
              </div>
            )}
          </footer>
        )}
      </Card>
    </article>
  )
})

export function ChatThread({ messages, onCitationClick }: ChatThreadProps) {
  if (messages.length === 0) {
    return <div className={styles.empty}>提出第一个问题，开始与知识库对话</div>
  }

  return (
    <div className={styles.thread}>
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} onCitationClick={onCitationClick} />
      ))}
    </div>
  )
}
