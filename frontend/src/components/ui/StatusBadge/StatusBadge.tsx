import type { ReactNode } from 'react'
import styles from './StatusBadge.module.css'

export interface StatusBadgeProps {
  status: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  children: ReactNode
}

export function StatusBadge({ status, children }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[status]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {children}
    </span>
  )
}
