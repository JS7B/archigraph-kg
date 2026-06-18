import type { ReactNode } from 'react'
import styles from './Panel.module.css'

export interface PanelProps {
  title?: string
  eyebrow?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}

export function Panel({ title, eyebrow, actions, children, className }: PanelProps) {
  const hasHeader = Boolean(title || eyebrow || actions)
  const classes = [styles.panel, className ?? ''].filter(Boolean).join(' ')

  return (
    <section className={classes}>
      {hasHeader && (
        <header className={styles.header}>
          <div className={styles.heading}>
            {eyebrow && <span className={styles.eyebrow}>{eyebrow}</span>}
            {title && <h2 className={styles.title}>{title}</h2>}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      <div className={styles.body}>{children}</div>
    </section>
  )
}
