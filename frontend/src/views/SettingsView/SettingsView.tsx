import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { fetchHealthDeps, type HealthDeps } from '../../api/health'
import { Card, DataValue, Eyebrow, Panel, StatusBadge } from '../../components/ui'
import styles from './SettingsView.module.css'

/**
 * 设置页：依赖连通状态 + 模型配置提示 + 样本导入说明。
 *
 * - 依赖状态调 GET /health/deps 实时探测 Neo4j / LLM（只读展示，前端不改 .env）。
 * - 模型配置在后端 .env，这里只提示用户去配，不在前端修改。
 */

type Neo4jState = { label: string; status: 'success' | 'error' }
type LlmState = { label: string; status: 'success' | 'warning' }

function parseNeo4j(raw: string): Neo4jState {
  return raw === 'ok'
    ? { label: '已连接', status: 'success' }
    : { label: raw || '连接失败', status: 'error' }
}

function parseLlm(raw: string): LlmState {
  return raw === 'configured'
    ? { label: '已配置', status: 'success' }
    : { label: '未配置', status: 'warning' }
}

export function SettingsView() {
  const [health, setHealth] = useState<HealthDeps | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchHealthDeps()
      setHealth(data)
      setLoadError(null)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '请求失败，请确认后端已启动'
      setLoadError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const neo4j = health ? parseNeo4j(health.neo4j) : null
  const llm = health ? parseLlm(health.llm) : null

  return (
    <div className={styles.settings}>
      <header className={styles.header}>
        <Eyebrow>Settings</Eyebrow>
        <h1 className={styles.title}>设置</h1>
        <button className={styles.refreshBtn} onClick={() => void refresh()} disabled={loading}>
          {loading ? '检测中…' : '重新检测'}
        </button>
      </header>

      {loadError && <div className={styles.errorMsg}>检测失败：{loadError}</div>}

      <Panel eyebrow="Dependencies" title="依赖连通状态">
        <div className={styles.depGrid}>
          <Card padding="md" className={styles.depCard}>
            <div className={styles.depHead}>
              <span className={styles.depName}>Neo4j 图数据库</span>
              {neo4j ? (
                <StatusBadge status={neo4j.status}>{neo4j.label}</StatusBadge>
              ) : (
                <StatusBadge status="neutral">{loading ? '检测中' : '未知'}</StatusBadge>
              )}
            </div>
            <p className={styles.depDesc}>
              存储知识图谱与向量索引。Docker 本地部署，<code>docker compose up -d neo4j</code> 启动。
            </p>
          </Card>

          <Card padding="md" className={styles.depCard}>
            <div className={styles.depHead}>
              <span className={styles.depName}>LLM 服务</span>
              {llm ? (
                <StatusBadge status={llm.status}>{llm.label}</StatusBadge>
              ) : (
                <StatusBadge status="neutral">{loading ? '检测中' : '未知'}</StatusBadge>
              )}
            </div>
            <p className={styles.depDesc}>
              OpenAI-compatible 接口，用于实体抽取、向量生成与问答。
            </p>
          </Card>
        </div>
      </Panel>

      <Panel eyebrow="Model Config" title="模型配置">
        <p className={styles.bodyText}>
          模型配置在后端 <code>.env</code> 文件，前端不可直接修改。请编辑仓库根目录的
          <code> .env</code>，设置以下变量后重启后端：
        </p>
        <div className={styles.configList}>
          <DataValue label="OPENAI_BASE_URL">LLM 服务地址</DataValue>
          <DataValue label="OPENAI_API_KEY">API 密钥</DataValue>
          <DataValue label="CHAT_MODEL">对话模型名</DataValue>
          <DataValue label="EMBEDDING_MODEL">向量模型名</DataValue>
          <DataValue label="NEO4J_URI / PASSWORD">Neo4j 连接</DataValue>
        </div>
      </Panel>

      <Panel eyebrow="Getting Started" title="样本导入说明">
        <p className={styles.bodyText}>
          上传文档即可构建知识图谱。支持 Markdown（<code>.md</code>）、纯文本（<code>.txt</code>）、
          PDF（<code>.pdf</code>）。
        </p>
        <ol className={styles.steps}>
          <li>确认上方 Neo4j 与 LLM 已就绪（绿色）。</li>
          <li>进入「文档库」视图，点击「上传文档」。</li>
          <li>等待入库完成（像素档案员会显示进度），实体与关系自动写入图谱。</li>
          <li>在「图谱探索」查看实体关系，在「问答」向知识库提问。</li>
        </ol>
      </Panel>
    </div>
  )
}
