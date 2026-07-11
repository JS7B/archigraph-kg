import { useLayoutEffect } from 'react'
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { subscribeRunEvents } from '../api/sse'
import type { RunEvent } from '../types'
import { useRunEvents } from './useRunEvents'

vi.mock('../api/sse', () => ({
  subscribeRunEvents: vi.fn(),
}))

const runningEvent: RunEvent = {
  stage: 'searching',
  status: 'running',
  message: '正在检索',
  answer: null,
  timestampMs: 1,
}

const succeededEvent: RunEvent = {
  stage: 'idle',
  status: 'succeeded',
  message: '完成',
  answer: null,
  timestampMs: 2,
}

describe('useRunEvents', () => {
  const subscriptions = new Map<
    string,
    { emit: (event: RunEvent) => void; fail: (error: Event) => void }
  >()

  beforeEach(() => {
    vi.clearAllMocks()
    subscriptions.clear()
    vi.mocked(subscribeRunEvents).mockImplementation((runId, onEvent, onError) => {
      subscriptions.set(runId, { emit: onEvent, fail: onError })
      return vi.fn()
    })
  })

  it('clears old events when runId changes', () => {
    const { result, rerender } = renderHook(
      ({ runId }: { runId: string | null }) => useRunEvents(runId),
      { initialProps: { runId: 'run-a' } },
    )

    act(() => subscriptions.get('run-a')!.emit(runningEvent))
    expect(result.current.events).toEqual([runningEvent])
    expect(result.current.currentStage).toBe('searching')

    rerender({ runId: 'run-b' })

    expect(result.current.events).toEqual([])
    expect(result.current.currentStage).toBe('idle')
  })

  it('delivers one terminal callback per run', () => {
    const onTerminal = vi.fn()
    renderHook(() => useRunEvents('run-a', { onTerminal }))

    act(() => {
      subscriptions.get('run-a')!.emit(succeededEvent)
      subscriptions.get('run-a')!.emit(succeededEvent)
    })

    expect(onTerminal).toHaveBeenCalledTimes(1)
    expect(onTerminal).toHaveBeenCalledWith(succeededEvent)
  })

  it('ignores events, errors, and terminal callbacks from an obsolete run', () => {
    const onTerminal = vi.fn()
    const { result, rerender } = renderHook(
      ({ runId }: { runId: string }) => useRunEvents(runId, { onTerminal }),
      { initialProps: { runId: 'run-a' } },
    )
    const runA = subscriptions.get('run-a')!

    rerender({ runId: 'run-b' })
    act(() => {
      runA.emit(succeededEvent)
      runA.fail(new Event('error'))
    })

    expect(result.current.events).toEqual([])
    expect(result.current.currentStage).toBe('idle')
    expect(result.current.error).toBeNull()
    expect(onTerminal).not.toHaveBeenCalled()
  })

  it('ignores an obsolete run during the next run layout commit', () => {
    const onTerminal = vi.fn()
    const { result, rerender } = renderHook(
      ({ runId }: { runId: string }) => {
        const state = useRunEvents(runId, { onTerminal })
        useLayoutEffect(() => {
          if (runId === 'run-b') {
            subscriptions.get('run-a')!.emit(succeededEvent)
            subscriptions.get('run-a')!.fail(new Event('error'))
          }
        }, [runId])
        return state
      },
      { initialProps: { runId: 'run-a' } },
    )

    rerender({ runId: 'run-b' })

    expect(result.current.events).toEqual([])
    expect(result.current.currentStage).toBe('idle')
    expect(result.current.error).toBeNull()
    expect(onTerminal).not.toHaveBeenCalled()
  })

  it('uses the latest terminal callback without resubscribing', () => {
    const firstCallback = vi.fn()
    const latestCallback = vi.fn()
    const { rerender } = renderHook(
      ({ onTerminal }) => useRunEvents('run-a', { onTerminal }),
      { initialProps: { onTerminal: firstCallback } },
    )

    rerender({ onTerminal: latestCallback })
    expect(subscribeRunEvents).toHaveBeenCalledTimes(1)

    act(() => subscriptions.get('run-a')!.emit(succeededEvent))

    expect(firstCallback).not.toHaveBeenCalled()
    expect(latestCallback).toHaveBeenCalledOnce()
  })
})
