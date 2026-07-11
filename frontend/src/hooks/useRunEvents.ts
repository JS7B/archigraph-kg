import { useEffect, useRef, useState } from 'react'
import { subscribeRunEvents } from '../api/sse'
import type { RunEvent, Stage } from '../types'

export interface UseRunEventsOptions {
  onTerminal?: (event: RunEvent) => void
}

const TERMINAL = new Set(['succeeded', 'failed'])

/**
 * 运行事件流钩子。AgentRoom 与 RunEventTimeline 共享此唯一数据源，
 * 红线：currentStage 只从真实 RunEvent 派生，禁止前端编造（硬规则）。
 *
 * 传入 runId 后订阅 SSE，累积事件并派生当前 stage；runId 为 null 时不订阅。
 */
export function useRunEvents(runId: string | null, options: UseRunEventsOptions = {}) {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [currentStage, setCurrentStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)
  const [prevRunId, setPrevRunId] = useState(runId)
  const onTerminalRef = useRef(options.onTerminal)
  const handledTerminalRef = useRef(false)
  onTerminalRef.current = options.onTerminal

  // runId 一变（含变回 null）立即在渲染期清空事件，而非等 effect。否则 Run 结束
  // （runId→null）时旧终态事件会滞留在 events 里；下个 Run 起（null→newId）触发消费方的
  // 终态 effect 时，它读到的仍是上一轮残留的成功事件，把旧答案当本轮结果——即问答/上传
  // "慢一拍、要再发/再点一次" 的根因。渲染期重置保证消费方本帧就拿到空 events。
  if (runId !== prevRunId) {
    setPrevRunId(runId)
    setEvents([])
    setCurrentStage('idle')
    setError(null)
    handledTerminalRef.current = false
  }

  useEffect(() => {
    if (!runId) return

    const unsubscribe = subscribeRunEvents(
      runId,
      (event) => {
        setEvents((prev) => [...prev, event])
        setCurrentStage(event.stage)
        if (TERMINAL.has(event.status) && !handledTerminalRef.current) {
          handledTerminalRef.current = true
          onTerminalRef.current?.(event)
        }
      },
      () => setError('SSE 连接中断，请确认后端正在运行，稍后重新提问重试'),
    )
    return unsubscribe
  }, [runId])

  return { events, currentStage, error }
}
