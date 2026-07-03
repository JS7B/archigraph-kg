import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { Answer, ChatMessage, Citation } from '../../types'
import { Card, StatusBadge } from '../ui'
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

// 正文 [n] → [[n]](#cite-n) 链接语法，交给 markdown 的 a 覆写渲染成内联引用芯片。
// 后端角标净化正则保持不变，这里只做展示层的语法转换。
const CITE_MARKER = /\[(\d+)\]/g
function linkifyCitations(text: string): string {
  return text.replace(CITE_MARKER, '[[$1]](#cite-$1)')
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
// - #cite-n 链接 → 内联引用芯片（n 超范围则降级为纯文本 [n]）
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
        const bodyText = answer?.text ?? message.text
        const citations = answer?.citations ?? []
        const components = buildMarkdownComponents(citations, onCitationClick)

        return (
          <article key={message.id} className={`${styles.message} ${styles.agent}`}>
            <div className={styles.meta}>GraphRAG Agent</div>
            <Card className={styles.agentCard} padding="md">
              <div className={styles.answerText}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                  {linkifyCitations(bodyText)}
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
      })}
    </div>
  )
}
