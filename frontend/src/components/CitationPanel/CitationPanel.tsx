import type { Citation } from '../../types'

interface CitationPanelProps {
  citations: Citation[]
  activeChunkId: string | null
}

// 占位：展示引用原文；activeChunkId 命中的条目高亮（与 ChatThread 角标双向联动）。
export function CitationPanel({ citations, activeChunkId }: CitationPanelProps) {
  if (citations.length === 0) {
    return <div>引用证据将在回答生成后显示（占位）</div>
  }
  return (
    <div>
      {citations.map((c) => (
        <div
          key={c.index}
          style={{
            fontWeight: c.chunkId === activeChunkId ? 600 : 400,
          }}
        >
          [{c.index}] {c.documentName} · {c.location}：{c.snippet}
        </div>
      ))}
    </div>
  )
}
