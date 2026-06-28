// 后端基址。apiFetch 与 SSE 客户端共享，避免复制（规格 §SSE 关键设计点）。
export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// 轻量鉴权：配合后端 B2 的 X-API-Key 中间件。
// VITE_API_KEY 未配置时返回空对象（开发模式，后端 key 为空也会跳过校验）。
// 部署时在 .env 填 VITE_API_KEY 即启用；为空则放行。
const API_KEY = import.meta.env.VITE_API_KEY ?? ''

/** 构造鉴权 header（key 为空时不带，保持开发模式零配置）。 */
export function authHeaders(): Record<string, string> {
  return API_KEY ? { 'X-API-Key': API_KEY } : {}
}

// 对接后端统一错误结构 {"error": {"type", "message"}}。
export class ApiError extends Error {
  type: string
  constructor(type: string, message: string) {
    super(message)
    this.type = type
    this.name = 'ApiError'
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    ...init,
  })
  if (!res.ok) {
    let type = 'http_error'
    let message = res.statusText
    try {
      const body = await res.json()
      if (body?.error) {
        type = body.error.type ?? type
        message = body.error.message ?? message
      }
    } catch {
      // 响应非 JSON，沿用 statusText
    }
    throw new ApiError(type, message)
  }
  return res.json() as Promise<T>
}
