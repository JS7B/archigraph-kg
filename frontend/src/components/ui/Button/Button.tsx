import type { ButtonHTMLAttributes, ReactNode } from 'react'
import styles from './Button.module.css'

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md'
  disabled?: boolean
  type?: ButtonHTMLAttributes<HTMLButtonElement>['type']
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>['onClick']
  children: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  type = 'button',
  disabled = false,
  onClick,
  children,
}: ButtonProps) {
  return (
    <button
      className={`${styles.button} ${styles[variant]} ${styles[size]}`}
      disabled={disabled}
      type={type}
      onClick={onClick}
    >
      {children}
    </button>
  )
}
