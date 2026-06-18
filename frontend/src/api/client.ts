const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

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
    headers: { 'Content-Type': 'application/json' },
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
