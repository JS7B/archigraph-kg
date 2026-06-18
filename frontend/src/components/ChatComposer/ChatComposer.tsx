import { useState } from 'react'

interface ChatComposerProps {
  onSend: (text: string) => void
}

export function ChatComposer({ onSend }: ChatComposerProps) {
  const [text, setText] = useState('')
  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      <input
        style={{ flex: 1, padding: 'var(--space-2)' }}
        value={text}
        placeholder="向知识库提问…"
        onChange={(e) => setText(e.target.value)}
      />
      <button
        onClick={() => {
          if (text.trim()) {
            onSend(text)
            setText('')
          }
        }}
      >
        发送
      </button>
    </div>
  )
}
