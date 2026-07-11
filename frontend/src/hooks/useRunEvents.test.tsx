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
  let emit: (event: RunEvent) => void

  beforeEach(() => {
    vi.mocked(subscribeRunEvents).mockImplementation((_runId, onEvent) => {
      emit = onEvent
      return vi.fn()
    })
  })

  it('clears old events when runId changes', () => {
    const { result, rerender } = renderHook(
      ({ runId }: { runId: string | null }) => useRunEvents(runId),
      { initialProps: { runId: 'run-a' } },
    )

    act(() => emit(runningEvent))
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
      emit(succeededEvent)
      emit(succeededEvent)
    })

    expect(onTerminal).toHaveBeenCalledTimes(1)
    expect(onTerminal).toHaveBeenCalledWith(succeededEvent)
  })
})
