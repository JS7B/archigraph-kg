import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/client'
import { createConversation, getConversation, listConversations } from '../../api/conversations'
import { useRunEvents } from '../../hooks/useRunEvents'
import type { RunEvent } from '../../types'
import { WorkbenchView } from './WorkbenchView'

vi.mock('../../api/client', () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {},
}))

vi.mock('../../api/conversations', () => ({
  listConversations: vi.fn(),
  createConversation: vi.fn(),
  getConversation: vi.fn(),
  renameConversation: vi.fn(),
  deleteConversation: vi.fn(),
}))

vi.mock('../../hooks/useRunEvents', () => ({
  useRunEvents: vi.fn(),
}))

vi.mock('../../components/AgentRoom/AgentRoom', () => ({
  AgentRoom: () => null,
}))

const conversation = {
  conversationId: 'conv-1',
  title: '会话一',
  createdAt: 1,
  messageCount: 0,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('WorkbenchView terminal flow', () => {
  let onTerminal: ((event: RunEvent) => void) | undefined

  beforeEach(() => {
    vi.clearAllMocks()
    onTerminal = undefined
    vi.mocked(listConversations).mockResolvedValue({ items: [conversation] })
    vi.mocked(getConversation).mockResolvedValue({ ...conversation, messages: [] })
    vi.mocked(apiFetch).mockResolvedValue({ runId: 'run-followup', conversationId: 'conv-1' })
    vi.mocked(useRunEvents).mockImplementation((_runId, options) => {
      onTerminal = options?.onTerminal
      return { events: [], currentStage: 'idle', error: null }
    })
  })

  afterEach(cleanup)

  it('appends one successful answer and keeps the current conversation', async () => {
    render(<WorkbenchView />)

    fireEvent.click(await screen.findByText('会话一'))
    const composer = await screen.findByLabelText('向知识库提问')
    await waitFor(() => expect(composer).toBeEnabled())

    expect(onTerminal).toBeTypeOf('function')
    await act(async () => {
      onTerminal?.({
        stage: 'idle',
        status: 'succeeded',
        message: '完成',
        answer: { text: '来自知识图谱的回答', confidence: 'high', citations: [] },
        timestampMs: 10,
      })
      await Promise.resolve()
    })

    expect(await screen.findByText('来自知识图谱的回答')).toBeInTheDocument()
    expect(composer).toBeEnabled()
    await waitFor(() => expect(listConversations).toHaveBeenCalledTimes(2))

    fireEvent.change(composer, { target: { value: '继续追问' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ question: '继续追问', conversationId: 'conv-1' }),
      })
    })
  })

  it('does not let the initial list overwrite a newly created conversation', async () => {
    const initialList = deferred<{ items: (typeof conversation)[] }>()
    vi.mocked(listConversations).mockReturnValueOnce(initialList.promise)
    vi.mocked(createConversation).mockResolvedValue({
      conversationId: 'conv-new',
      title: '刚创建的会话',
      createdAt: 2,
      messageCount: 0,
      messages: [],
    })

    render(<WorkbenchView />)
    fireEvent.click(screen.getByRole('button', { name: '新建会话' }))
    await waitFor(() => expect(screen.getByLabelText('向知识库提问')).toBeEnabled())

    await act(async () => {
      initialList.resolve({ items: [conversation] })
      await initialList.promise
    })

    expect(screen.getByText('刚创建的会话')).toBeInTheDocument()
    expect(screen.queryByText('会话一')).not.toBeInTheDocument()
  })
})
