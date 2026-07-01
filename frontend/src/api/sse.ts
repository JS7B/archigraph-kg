import type { RunEvent, RunEventStatus, Stage } from '../types'
import { BASE_URL } from './client'

/**
 * SSE（Server-Sent Events）订阅：浏览器原生 EventSource 监听后端进度流。
 *
 * 后端 /api/runs/{runId}/events/stream 持续推送 RunEvent，前端每收一条更新 UI；
 * 收到终态事件（status=succeeded|failed）后后端会主动关闭流，前端也立即 close，
 * 不留僵尸连接（不关闭会一直挂着，泄漏连接数）。
 *
 * 终态兜底（修 SSE 终态丢失 bug）：后端 yield 终态事件后立即关闭连接，
 * sse-starlette 的关闭时序可能导致最后一条事件没真正 flush 到浏览器（EventSource
 * 异步读，连接关太快就丢）。故在 onerror（连接关闭/异常）时，主动查一次
 * /api/runs/{runId}/events 历史接口补全可能丢失的终态——SSE 推进度，HTTP 兜终态。
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

/** 把后端历史接口返回的原始对象解析校验成 RunEvent（与 onmessage 同口径）。 */
function parseEvent(obj: Record<string, unknown>): RunEvent | null {
  if (!isStage(obj.stage)) return null
  const status = obj.status as RunEventStatus
  if (status !== 'running' && status !== 'succeeded' && status !== 'failed') return null
  return {
    stage: obj.stage,
    status,
    message: typeof obj.message === 'string' ? obj.message : '',
    answer: (obj.answer as RunEvent['answer']) ?? null,
    timestampMs: typeof obj.timestampMs === 'number' ? obj.timestampMs : Date.now(),
  }
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
  // closed 标志：组件卸载或终态已处理后，屏蔽异步兜底回调，防止状态泄漏到下一个 Run。
  let closed = false

  source.onmessage = (msg: MessageEvent<string>) => {
    let parsed: unknown
    try {
      parsed = JSON.parse(msg.data)
    } catch {
      return
    }
    if (!parsed || typeof parsed !== 'object') return
    const event = parseEvent(parsed as Record<string, unknown>)
    if (!event) return

    onEvent(event)

    // 终态：立即关闭，释放连接。后端也会在发完终态事件后断流，这里是双保险。
    if (TERMINAL_STATUSES.has(event.status)) {
      closed = true // 标记已处理终态，屏蔽后续兜底查询
      source.close()
    }
  }

  // onerror 在网络中断或服务端关闭时触发。
  // 终态已正常 close（readyState=CLOSED）→ 跳过；异常中断 → 查历史补全终态。
  source.onerror = (err: Event) => {
    if (source.readyState === EventSource.CLOSED || closed) return
    source.close()
    closed = true

    // 终态兜底：SSE 可能丢失终态（sse-starlette 关闭时序），查历史接口补全。
    // 历史里有终态则补投 onEvent（让 useRunEvents 的终态处理正常触发 refresh）；
    // 查不到终态（Run 仍在跑/查询失败）则照常报错。
    fetch(`${BASE_URL}/api/runs/${runId}/events`)
      .then((r) => (r.ok ? r.json() : []))
      .then((raw: unknown[]) => {
        if (!Array.isArray(raw) || raw.length === 0) {
          onError(err)
          return
        }
        const last = parseEvent(raw[raw.length - 1] as Record<string, unknown>)
        if (last && TERMINAL_STATUSES.has(last.status)) {
          onEvent(last) // 补投终态，避免前端"卡在 indexing 永远不刷新"
        } else {
          onError(err) // 历史里还没终态，按异常中断处理
        }
      })
      .catch(() => onError(err))
  }

  return () => {
    closed = true
    source.close()
  }
}
