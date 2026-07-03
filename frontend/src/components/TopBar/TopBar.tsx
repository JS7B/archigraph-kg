import { useEffect, useState } from 'react'
import styles from './TopBar.module.css'
import { Button } from '../ui'
import { GearIcon } from '../ui/Icon/Icon'
import { fetchHealthDeps, type HealthDeps } from '../../api/health'

export type ViewKey = 'workbench' | 'library' | 'graph'

const TABS: { key: ViewKey; label: string }[] = [
  { key: 'workbench', label: '问答' },
  { key: 'library', label: '文档库' },
  { key: 'graph', label: '图谱' },
]

// F10 依赖探针轮询间隔：30 秒一次，够及时又不扰民（探针是只读 GET，开销小）。
const HEALTH_POLL_MS = 30_000

interface TopBarProps {
  active: ViewKey
  onChange: (v: ViewKey) => void
  onToggleSettings: () => void
}

export function TopBar({ active, onChange, onToggleSettings }: TopBarProps) {
  // F10 状态灯接 /health/deps：'unknown'(拉取前/失败) | HealthDeps
  const [deps, setDeps] = useState<HealthDeps | null>(null)

  useEffect(() => {
    let alive = true
    const poll = async () => {
      try {
        const d = await fetchHealthDeps()
        if (alive) setDeps(d)
      } catch {
        // 拉取失败保留上一次结果（或 null=未知），不抛错扰民
      }
    }
    void poll()
    const timer = setInterval(poll, HEALTH_POLL_MS)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  // Neo4j: 'ok' 视为通；llm: 'configured' 视为通。
  const neo4jOk = deps?.neo4j === 'ok'
  const llmOk = deps?.llm === 'configured'

  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.dot} />
        Archigraph · 档图
      </div>
      <nav className={styles.tabs} aria-label="主导航">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={t.key === active ? styles.tabActive : styles.tab}
            aria-current={t.key === active ? 'page' : undefined}
            onClick={() => onChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className={styles.status}>
        {/* F10 状态灯：绿=通、红=断、灰=未知，配 aria-label 朗读语义 */}
        <span
          className={`${styles.depDot} ${neo4jOk ? styles.dotOk : deps ? styles.dotFail : styles.dotUnknown}`}
          aria-label={`Neo4j ${neo4jOk ? '已连接' : deps ? '连接失败' : '未知'}`}
          role="img"
        />
        <span
          className={`${styles.depDot} ${llmOk ? styles.dotOk : deps ? styles.dotFail : styles.dotUnknown}`}
          aria-label={`LLM ${llmOk ? '已配置' : deps ? '未配置' : '未知'}`}
          role="img"
        />
        <Button className={styles.settingsBtn} size="sm" onClick={onToggleSettings} aria-label="设置">
          <GearIcon size={14} /> 设置
        </Button>
      </div>
    </header>
  )
}
