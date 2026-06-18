import type { ReactNode } from 'react'
import styles from './Eyebrow.module.css'

export interface EyebrowProps {
  children: ReactNode
  className?: string
}

export function Eyebrow({ children, className }: EyebrowProps) {
  const classes = [styles.eyebrow, className ?? ''].filter(Boolean).join(' ')

  return <span className={classes}>{children}</span>
}
