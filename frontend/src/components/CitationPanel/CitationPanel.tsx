import { useEffect, useRef } from 'react'
import type { Citation } from '../../types'
import { DataValue } from '../ui'
import styles from './CitationPanel.module.css'

interface CitationPanelProps {
  citations: Citation[]
  activeChunkId: string | null
}

export function CitationPanel({ citations, activeChunkId }: CitationPanelProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLElement>(null)

  // 角标被点击 → activeChunkId 变化 → 滚动到对应来源条目。
  // 仅在列表内滚动（block: 'nearest'），不牵动整页。
  useEffect(() => {
    if (!activeChunkId || !activeRef.current) return
    activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [activeChunkId])

  if (citations.length === 0) {
    return <div className={styles.empty}>引用证据将在回答生成后显示</div>
  }

  return (
    <div className={styles.panel}>
      <div ref={listRef} className={styles.list}>
        {citations.map((citation) => {
          const isActive = citation.chunkId === activeChunkId

          return (
            <article
              key={`${citation.chunkId}-${citation.index}`}
              ref={isActive ? activeRef : null}
              className={`${styles.entry} ${isActive ? styles.active : ''}`}
              aria-current={isActive ? 'true' : undefined}
            >
              <sup className={styles.index}>[{citation.index}]</sup>
              <div className={styles.body}>
                <div className={styles.source}>
                  <strong className={styles.documentName}>{citation.documentId}</strong>
                  <DataValue label="loc">{citation.location}</DataValue>
                </div>
                <div className={styles.trace}>
                  <DataValue label="chunk">{citation.chunkId}</DataValue>
                </div>
                <p className={styles.snippet}>{citation.snippet}</p>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
