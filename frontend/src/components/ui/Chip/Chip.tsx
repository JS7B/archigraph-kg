import type { ReactNode } from 'react'
import styles from './Chip.module.css'

export interface ChipProps {
  children: ReactNode
  tone?: 'neutral' | 'accent'
  className?: string
}

export function Chip({ children, tone = 'neutral', className }: ChipProps) {
  const classes = [styles.chip, styles[tone], className ?? ''].filter(Boolean).join(' ')

  return <span className={classes}>{children}</span>
}
