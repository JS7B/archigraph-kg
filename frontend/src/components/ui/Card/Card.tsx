import type { ElementType, ReactNode } from 'react'
import styles from './Card.module.css'

export interface CardProps {
  as?: ElementType
  padding?: 'sm' | 'md' | 'lg'
  interactive?: boolean
  children: ReactNode
  className?: string
}

export function Card({
  as: Component = 'section',
  padding = 'md',
  interactive = false,
  children,
  className,
}: CardProps) {
  const classes = [
    styles.card,
    styles[padding],
    interactive ? styles.interactive : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')

  return <Component className={classes}>{children}</Component>
}
