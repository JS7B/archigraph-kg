import { useEffect, useRef } from 'react'
import type { Stage } from '../../types'

/**
 * useAgentPosition · 小人横向位置的状态机式插值驱动。
 *
 * 解决的问题（纯 CSS transition 做不到的）：
 *   stage 快速连续变化时，"从当前真实像素位置（含动画中间帧）"重新锁定目标，
 *   而不是从 CSS 计算起点瞬移。即用户要的"中断即转"。
 *
 * 机制：
 *   1) currentXRef 始终记录小人当前真实 left（每帧更新，含插值中间帧）。
 *   2) stage 变化 → useEffect → 以 currentXRef.current 为起点，rAF 逐帧插值到目标。
 *   3) 中途 stage 再变 → effect cleanup 取消旧 rAF → 新 effect 以此时真实位置为起点
 *      重新开始插值 = 中断即转。提速到 0.4s 减少"走回头路"的不自然感。
 *
 * 为什么直接写 style.left 而不进 React state：
 *   60fps 逐帧进 state 会触发高频 re-render，性能差且无必要——位置是纯视觉，
 *   直接写 DOM 即可（ref 读取 / 写入），不参与 React 渲染。currentXRef 用 ref
 *   同样是为了不触发 re-render 但能跨帧保留真实值。
 */

// 12 状态 → 目标 left（百分比，与画布宽度相除）。保持与原 CSS [data-stage] 规则一致。
const STAGE_X: Record<Stage, number> = {
  idle: 16,
  uploading: 50,
  parsing: 50,
  extracting: 50,
  linking: 48,
  indexing: 74,
  searching: 74,
  writing: 14,
  checking: 14,
  deleting: 86,
  rebuilding: 86,
  error: 50,
}

// 飘移时长（ms）。中断即转时用更短时长，减少"走回头路"的不自然感。
const MOVE_MS = 800
const MOVE_MS_INTERRUPTED = 400

// 缓动：ease-in-out 近似（x∈[0,1]）。
function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
}

interface AgentPosition {
  dudeRef: React.RefObject<HTMLDivElement | null>
  shadowRef: React.RefObject<HTMLDivElement | null>
}

/**
 * @param stage 当前 stage（来自真实 RunEvent）
 * @returns dudeRef / shadowRef —— 分别绑到小人 div 与影子 div 上
 */
export function useAgentPosition(stage: Stage): AgentPosition {
  const dudeRef = useRef<HTMLDivElement | null>(null)
  const shadowRef = useRef<HTMLDivElement | null>(null)
  // 真实当前 left（百分比）。初始即本 stage 目标，避免首帧从 0 跳。
  const currentXRef = useRef(STAGE_X[stage])
  // 是否已发生过一次移动（首次进入 stage 不算"中断"）。
  const hasMovedRef = useRef(false)

  useEffect(() => {
    const dude = dudeRef.current
    const shadow = shadowRef.current
    if (!dude && !shadow) return

    const target = STAGE_X[stage]
    const start = currentXRef.current
    if (start === target) return // 已在目标点，无需动

    // 中断即转：若上一段移动尚未结束就来了新目标，用提速时长。
    const duration = hasMovedRef.current ? MOVE_MS_INTERRUPTED : MOVE_MS
    hasMovedRef.current = true
    const startTime = performance.now()

    let rafId = 0
    const tick = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1)
      const eased = easeInOut(t)
      const x = start + (target - start) * eased
      // 写真实位置：直接写 DOM（不进 state），同步更新 ref 供下次中断读取。
      if (dude) dude.style.left = `${x}%`
      if (shadow) shadow.style.left = `${x}%`
      currentXRef.current = x
      if (t < 1) {
        rafId = requestAnimationFrame(tick)
      }
    }
    rafId = requestAnimationFrame(tick)

    // cleanup：stage 变化时取消未完成的 rAF；真实位置已留在 currentXRef，下段从这出发。
    return () => cancelAnimationFrame(rafId)
  }, [stage])

  return { dudeRef, shadowRef }
}
