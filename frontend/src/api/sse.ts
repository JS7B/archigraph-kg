import type { RunEvent, RunEventStatus, Stage } from '../types'
import { BASE_URL } from './client'

/**
 * SSE（Server-Sent Events）订阅：浏览器原生 EventSource 监听后端进度流。
 *
 * 后端 /api/runs/{runId}/events/stream 持续推送 RunEvent，前端每收一条更新 UI；
 * 收到终态事件（status=succeeded|failed）后后端会主动关闭流，前端也立即 close，
 * 不留僵尸连接（不关闭会一直挂着，泄漏连接数）。
 *
 * 本轮简单优先：不做断线重连 + /events 历史补全，EventSource 自带重连够用。
 *
 * ⚠️ X-API-Key 鉴权限制（配合后端 B2）：浏览器原生 EventSource 不支持自定义 header，
 *    故 SSE 这层无法带 X-API-Key。开发模式（后端 API_KEY 为空）自动放行，无影响；
 *    若生产环境配置了 API_KEY，需改用 fetch-based SSE（ReadableStream）重写本订阅，
 *    或后端为 /events/stream 开查询参数 / 放行白名单。当前未配置 API_KEY 故保持简单。
 */

const TERMINAL_STATUSES: ReadonlySet<RunEventStatus> = new Set(['succeeded', 'failed'])

function isStage(value: unknown): value is Stage {
  return (
    typeof value === 'string' &&
    [
      'idle', 'uploading', 'parsing', 'extracting', 'linking', 'indexing',
      'searching', 'checking', 'writing', 'deleting', 'rebuilding', 'error',
    ].includes(value)
  )
}

/**
 * 订阅一个 Run 的进度事件流。
 * @returns 取消订阅函数（关闭 EventSource），供 useEffect cleanup 调用。
 */
export function subscribeRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError: (err: Event) => void,
): () => void {
  const source = new EventSource(`${BASE_URL}/api/runs/${runId}/events/stream`)

  source.onmessage = (msg: MessageEvent<string>) => {
    // 后端每条事件以 JSON 字符串放在 data 字段，前端解析校验后交给上层。
    let parsed: unknown
    try {
      parsed = JSON.parse(msg.data)
    } catch {
      // 非法 payload 直接丢弃，不影响后续事件。
      return
    }
    if (!parsed || typeof parsed !== 'object') return
    const obj = parsed as Record<string, unknown>
    if (!isStage(obj.stage)) return
    const status = obj.status
    if (status !== 'running' && status !== 'succeeded' && status !== 'failed') return

    const event: RunEvent = {
      stage: obj.stage,
      status,
      message: typeof obj.message === 'string' ? obj.message : '',
      answer: (obj.answer as RunEvent['answer']) ?? null,
      // 后端 B8：timestamp_ms 已加 alias="timestampMs"，输出 camelCase。
      timestampMs: typeof obj.timestampMs === 'number' ? obj.timestampMs : Date.now(),
    }

    onEvent(event)

    // 终态：立即关闭，释放连接。后端也会在发完终态事件后断流，这里是双保险。
    if (TERMINAL_STATUSES.has(status)) {
      source.close()
    }
  }

  // onerror 在网络中断或服务端关闭时触发。终态已 close 后再触发 onerror 也无害。
  source.onerror = (err: Event) => {
    if (source.readyState === EventSource.CLOSED) return
    source.close()
    onError(err)
  }

  return () => source.close()
}
