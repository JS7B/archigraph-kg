import { useMemo } from 'react'
import type { RunEvent, Stage } from '../types'

// 运行事件流钩子。RunEventTimeline 与 PixelAgentStage 共享此唯一数据源，
// 保证"小人动作 = 真实事件"。
//
// 占位实现：当前返回空事件流。后端就绪后，这里改为订阅
// SSE  /api/runs/{runId}/events/stream，把收到的 RunEvent 累积进 events。
// 红线：currentStage 只能从真实 events 派生，禁止前端编造。
export function useRunEvents(): { events: RunEvent[]; currentStage: Stage } {
  const events: RunEvent[] = useMemo(() => [], [])
  const currentStage: Stage =
    events.length > 0 ? events[events.length - 1].stage : 'idle'
  return { events, currentStage }
}
