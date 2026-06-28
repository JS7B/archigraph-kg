import type { Answer } from './answer'

// 像素 Agent 的 12 个工作状态。顺序与规格 §4 一致。
export type Stage =
  | 'idle'
  | 'uploading'
  | 'parsing'
  | 'extracting'
  | 'linking'
  | 'indexing'
  | 'searching'
  | 'checking'
  | 'writing'
  | 'deleting'
  | 'rebuilding'
  | 'error'

// 对齐后端 RunStatus：'running' | 'succeeded' | 'failed'。
// 终态（succeeded/failed）事件到达后 SSE 流由后端关闭、前端 EventSource 释放。
export type RunEventStatus = 'running' | 'succeeded' | 'failed'

// 后端推送的单条运行事件。字段名严格对齐后端 by_alias 输出（详见规格 §契约对齐）。
// - 终态成功事件 stage='idle' + status='succeeded'，判终态用 status 而非 stage。
// - timestampMs：后端 B8 已加 alias="timestampMs"，统一 camelCase 输出。
// - answer：仅问答终态(succeeded)事件携带，其余为 null。
export interface RunEvent {
  stage: Stage
  status: RunEventStatus
  message: string
  answer: Answer | null
  timestampMs: number
}
