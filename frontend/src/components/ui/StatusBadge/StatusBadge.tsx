import type { ReactNode } from 'react'
import styles from './StatusBadge.module.css'

export interface StatusBadgeProps {
  status: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  children: ReactNode
  className?: string
}

export function StatusBadge({ status, children, className = '' }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[status]} ${className}`}>
      <span className={styles.dot} aria-hidden="true" />
      {children}
    </span>
  )
}
