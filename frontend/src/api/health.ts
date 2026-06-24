import { apiFetch } from './client'

/**
 * 健康检查 API：依赖探针透传。
 *
 * 后端 /health/deps 探测 Neo4j 与 LLM 配置状态，任何失败降级为文本不抛 500。
 * - neo4j: 'ok' 或 'error: ...'（连通/失败）
 * - llm: 'configured' 或 'not_configured'
 */
export interface HealthDeps {
  neo4j: string
  llm: 'configured' | 'not_configured'
}

/** GET /health/deps → {neo4j, llm}（直接透传，不做映射） */
export async function fetchHealthDeps(): Promise<HealthDeps> {
  return apiFetch<HealthDeps>('/health/deps')
}
