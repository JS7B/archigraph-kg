import type { RunEvent } from '../../types'
import styles from './RunEventTimeline.module.css'

interface RunEventTimelineProps {
  events: RunEvent[]
}

// 占位：时间倒序渲染事件，最新（当前阶段）高亮。与 PixelAgentStage 共享同一事件源。
export function RunEventTimeline({ events }: RunEventTimelineProps) {
  if (events.length === 0) {
    return <div className={styles.empty}>暂无运行事件（占位）</div>
  }
  return (
    <ul className={styles.list}>
      {[...events].reverse().map((e, i) => (
        <li key={e.timestamp} className={i === 0 ? styles.current : styles.item}>
          ▸ {e.stage} · {e.message}
        </li>
      ))}
    </ul>
  )
}
