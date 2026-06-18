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

export type RunEventStatus = 'started' | 'progress' | 'done' | 'failed'

// 后端推送的单条运行事件（前端需求版，字段名待后端契约协商）。
export interface RunEvent {
  stage: Stage
  status: RunEventStatus
  message: string
  timestamp: number // 毫秒时间戳
}
