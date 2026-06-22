import { useEffect, useState } from 'react'
import { subscribeRunEvents } from '../api/sse'
import type { RunEvent, Stage } from '../types'

/**
 * 运行事件流钩子。RunEventTimeline 与 PixelAgentStage 共享此唯一数据源，
 * 红线：currentStage 只从真实 RunEvent 派生，禁止前端编造（硬规则）。
 *
 * 传入 runId 后订阅 SSE，累积事件并派生当前 stage；runId 为 null 时不订阅。
 */
export function useRunEvents(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [currentStage, setCurrentStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return

    // 每次切换 runId 重置状态，避免上一个 Run 的事件残留。
    setEvents([])
    setCurrentStage('idle')
    setError(null)

    const unsubscribe = subscribeRunEvents(
      runId,
      (event) => {
        setEvents((prev) => [...prev, event])
        setCurrentStage(event.stage)
      },
      () => setError('SSE 连接中断'),
    )
    return unsubscribe
  }, [runId])

  return { events, currentStage, error }
}
