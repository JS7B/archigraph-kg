import styles from './TopBar.module.css'

export type ViewKey = 'workbench' | 'library' | 'graph'

const TABS: { key: ViewKey; label: string }[] = [
  { key: 'workbench', label: '问答' },
  { key: 'library', label: '文档库' },
  { key: 'graph', label: '图谱' },
]

interface TopBarProps {
  active: ViewKey
  onChange: (v: ViewKey) => void
  onOpenSettings: () => void
}

export function TopBar({ active, onChange, onOpenSettings }: TopBarProps) {
  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.dot} />
        GraphRAG 工作台
      </div>
      <nav className={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={t.key === active ? styles.tabActive : styles.tab}
            onClick={() => onChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className={styles.status}>
        {/* 依赖状态灯占位：后续接 /health/deps */}
        <span className={styles.depLabel}>Neo4j ●</span>
        <span className={styles.depLabel}>LLM ●</span>
        <button className={styles.settingsBtn} onClick={onOpenSettings}>
          ⚙ 设置
        </button>
      </div>
    </header>
  )
}
