import type { RunEvent, RunEventStatus } from '../../types'
import { Chip, DataValue } from '../ui'
import styles from './RunEventTimeline.module.css'

interface RunEventTimelineProps {
  events: RunEvent[]
}

const statusLabel: Record<RunEventStatus, string> = {
  running: 'running',
  succeeded: 'succeeded',
  failed: 'failed',
}

const statusClass: Record<RunEventStatus, string> = {
  running: styles.statusStarted,
  succeeded: styles.statusDone,
  failed: styles.statusFailed,
}

export function RunEventTimeline({ events }: RunEventTimelineProps) {
  if (events.length === 0) {
    return <div className={styles.empty}>暂无运行事件</div>
  }

  return (
    <ul className={styles.list}>
      {[...events].reverse().map((event, index) => {
        const isCurrent = index === 0
        const timeLabel = new Intl.DateTimeFormat('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }).format(event.timestampMs)

        return (
          <li
            key={`${event.stage}-${event.status}-${event.timestampMs}`}
            className={`${styles.item} ${isCurrent ? styles.current : ''}`}
          >
            <span className={styles.marker} aria-hidden="true" />
            <div className={styles.content}>
              <div className={styles.topLine}>
                <DataValue label="stage">{event.stage}</DataValue>
                <Chip className={statusClass[event.status]}>{statusLabel[event.status]}</Chip>
              </div>
              <p className={styles.message}>{event.message}</p>
              <time className={styles.time} dateTime={new Date(event.timestampMs).toISOString()}>
                {timeLabel}
              </time>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
