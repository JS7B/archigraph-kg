import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from '../../api/client'
import { useRunEvents } from '../../hooks/useRunEvents'
import type { DocumentMeta, RunEvent } from '../../types'
import { LibraryView } from './LibraryView'

vi.mock('../../api/client', () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {},
  BASE_URL: 'http://localhost:8000',
}))

vi.mock('../../hooks/useRunEvents', () => ({
  useRunEvents: vi.fn(),
}))

const document: DocumentMeta = {
  id: 'doc-1',
  name: 'notes.md',
  sourceType: 'markdown',
  parseStatus: 'parsed',
  indexStatus: 'indexed',
  chunkCount: 3,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('LibraryView terminal flow', () => {
  let onTerminal: ((event: RunEvent) => void) | undefined

  beforeEach(() => {
    vi.clearAllMocks()
    onTerminal = undefined
    vi.mocked(apiFetch).mockImplementation((path) => {
      if (path === '/api/documents') return Promise.resolve([document])
      return Promise.resolve({ runId: 'run-delete', documentId: document.id })
    })
    vi.mocked(useRunEvents).mockImplementation((_runId, options) => {
      onTerminal = options?.onTerminal
      return { events: [], currentStage: 'idle', error: null }
    })
  })

  afterEach(cleanup)

  it('clears library busy state and refreshes after success', async () => {
    render(<LibraryView />)

    expect(await screen.findByText('notes.md')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除' }))

    const uploadButton = screen.getAllByRole('button', { name: '上传文档' })[0]
    await waitFor(() => expect(uploadButton).toBeDisabled())
    expect(onTerminal).toBeTypeOf('function')

    await act(async () => {
      onTerminal?.({
        stage: 'idle',
        status: 'succeeded',
        message: '删除完成',
        answer: null,
        timestampMs: 10,
      })
      await Promise.resolve()
    })

    await waitFor(() => expect(uploadButton).toBeEnabled())
    await waitFor(() => {
      const listCalls = vi.mocked(apiFetch).mock.calls.filter(([path]) => path === '/api/documents')
      expect(listCalls).toHaveLength(2)
    })
  })

  it('clears library busy state without refreshing after failure', async () => {
    render(<LibraryView />)

    expect(await screen.findByText('notes.md')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除' }))

    const uploadButton = screen.getAllByRole('button', { name: '上传文档' })[0]
    await waitFor(() => expect(uploadButton).toBeDisabled())
    expect(onTerminal).toBeTypeOf('function')

    act(() => {
      onTerminal?.({
        stage: 'error',
        status: 'failed',
        message: '删除失败',
        answer: null,
        timestampMs: 11,
      })
    })

    await waitFor(() => expect(uploadButton).toBeEnabled())
    expect(screen.getByText('删除失败')).toBeInTheDocument()
    const listCalls = vi.mocked(apiFetch).mock.calls.filter(([path]) => path === '/api/documents')
    expect(listCalls).toHaveLength(1)
  })

  it('keeps the newest document list when refresh responses finish out of order', async () => {
    const firstRefresh = deferred<DocumentMeta[]>()
    const latestRefresh = deferred<DocumentMeta[]>()
    let listRequest = 0
    vi.mocked(apiFetch).mockImplementation((path) => {
      if (path !== '/api/documents') {
        return Promise.resolve({ runId: 'run-delete', documentId: document.id })
      }
      listRequest += 1
      if (listRequest === 1) return Promise.resolve([document])
      if (listRequest === 2) return firstRefresh.promise
      return latestRefresh.promise
    })
    const newest = { ...document, id: 'doc-newest', name: 'newest.md' }
    const stale = { ...document, id: 'doc-stale', name: 'stale.md' }

    render(<LibraryView />)
    expect(await screen.findByText('notes.md')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '刷新文档列表' }))
    fireEvent.click(screen.getByRole('button', { name: '刷新文档列表' }))

    await act(async () => {
      latestRefresh.resolve([newest])
      await latestRefresh.promise
    })
    expect(screen.getByText('newest.md')).toBeInTheDocument()

    await act(async () => {
      firstRefresh.resolve([stale])
      await firstRefresh.promise
    })
    expect(screen.getByText('newest.md')).toBeInTheDocument()
    expect(screen.queryByText('stale.md')).not.toBeInTheDocument()
  })
})
