import type { ReactNode } from 'react'
import styles from './DataValue.module.css'

export interface DataValueProps {
  children: ReactNode
  label?: string
  className?: string
}

export function DataValue({ children, label, className }: DataValueProps) {
  const classes = [styles.dataValue, className ?? ''].filter(Boolean).join(' ')

  return (
    <span className={classes}>
      {label && <span className={styles.label}>{label}</span>}
      <span className={styles.value}>{children}</span>
    </span>
  )
}
