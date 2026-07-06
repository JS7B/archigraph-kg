import { useEffect, useRef } from 'react'
import type { Stage } from '../../types'
import {
  STAGE_HOME,
  nextIdleScript,
  previewBehavior,
  workScript,
  type Behavior,
} from './behaviors'

/**
 * useAgentPosition · 小人「行为队列状态机」驱动（位置 rAF 插值 + 微动作 data-action）。
 *
 * 从「stage → 单一落点」升级为「stage → 一段行为剧本」：
 *   - 一个行为 = 目标工位 x + 到位后的微动作 + 停留时长（见 behaviors.ts）。
 *   - 逐个消费行为：先走到 x（rAF 插值），到位后写 data-action 停留 ms，再取下一个。
 *   - 队列空则续排：工作 stage 循环剧本 / idle 加权随机续排（8~20s 间隔）。
 *
 * 保留原有两条关键性质：
 *   1) 位置直接写 DOM（不进 state）：60fps 逐帧不触发 re-render。
 *   2) 中断即转：stage 变 → effect cleanup 取消当前 rAF/timeout → 新 effect 以
 *      currentXRef（真实当前位置）为起点重排剧本。
 *
 * data-action 写在 canvas 上（React 只控 data-stage/data-busy，不碰 data-action），
 * CSS 据 [data-action] 渲染姿态与手持文件 / zzz 气泡等道具（roomScenes.css）。
 *
 * 无障碍：prefers-reduced-motion 时不走动、不排剧本，仅静立呼吸（红线要求）。
 * 预览（StyleGallery）：只摆出该 stage 剧本首帧的静态位置与动作，不循环。
 */

// 缓动：ease-in-out 近似（x∈[0,1]）。
function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
}

interface AgentPosition {
  dudeRef: React.RefObject<HTMLDivElement | null>
  shadowRef: React.RefObject<HTMLDivElement | null>
  canvasRef: React.RefObject<HTMLDivElement | null>
}

/**
 * @param stage 当前 stage（来自真实 RunEvent）
 * @param preview true 时只摆静态首帧（StyleGallery 目录预览用）
 */
export function useAgentPosition(stage: Stage, preview = false): AgentPosition {
  const dudeRef = useRef<HTMLDivElement | null>(null)
  const shadowRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLDivElement | null>(null)
  // 真实当前 left（百分比）。初始即本 stage 落点，避免首帧从 0 跳。
  const currentXRef = useRef(STAGE_HOME[stage])

  useEffect(() => {
    const setX = (x: number) => {
      if (dudeRef.current) dudeRef.current.style.left = `${x}%`
      if (shadowRef.current) shadowRef.current.style.left = `${x}%`
      currentXRef.current = x
    }
    const setAction = (a: string) => {
      if (canvasRef.current) canvasRef.current.dataset.action = a
    }

    // 预览：静态摆出首帧位置 + 动作，不循环。
    if (preview) {
      const b = previewBehavior(stage)
      setX(b.x)
      setAction(b.action)
      return
    }

    // 减弱动效：不走动、不排剧本，静立在本 stage 落点仅呼吸。
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) {
      setX(STAGE_HOME[stage])
      setAction('idle-breathe')
      return
    }

    // ── 运行时：行为队列状态机 ──
    let cancelled = false
    let rafId = 0
    let timeoutId = 0
    const isIdle = stage === 'idle'
    let queue: Behavior[] = []

    // 队列空时续排下一段行为剧本；null = 该 stage 无剧本（error / 文档处理死 stage）→ 静立。
    const refill = (): Behavior | null => {
      if (isIdle) {
        queue = nextIdleScript(Math.random)
        return queue.shift() ?? null
      }
      const script = workScript(stage)
      if (script) {
        queue = script
        return queue.shift() ?? null
      }
      return null
    }

    const hold = (b: Behavior, done: () => void) => {
      setAction(b.action)
      timeoutId = window.setTimeout(() => {
        if (!cancelled) done()
      }, b.ms)
    }

    const play = (b: Behavior, done: () => void) => {
      const start = currentXRef.current
      const dist = Math.abs(b.x - start)
      if (dist < 0.5) {
        hold(b, done)
        return
      }
      // 走路阶段：搬文件段显示 carry（手持文件），否则普通 walk。时长按距离比例。
      setAction(b.carrying ? 'carry' : 'walk')
      const duration = Math.max(320, Math.round(dist * 16))
      const startTime = performance.now()
      const tick = (now: number) => {
        if (cancelled) return
        const t = Math.min((now - startTime) / duration, 1)
        setX(start + (b.x - start) * easeInOut(t))
        if (t < 1) {
          rafId = requestAnimationFrame(tick)
        } else {
          hold(b, done)
        }
      }
      rafId = requestAnimationFrame(tick)
    }

    const step = () => {
      if (cancelled) return
      const b = queue.shift() ?? refill()
      if (!b) {
        setAction('idle-breathe') // 无剧本 stage：静立（error 的抖动/红光由 [data-stage] 驱动）
        return
      }
      play(b, step)
    }

    setX(currentXRef.current) // 应用初值/上段真实位置
    step()

    // cleanup：stage 变化时取消未完成的 rAF/timeout；真实位置留在 currentXRef，下段从此出发。
    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      clearTimeout(timeoutId)
    }
  }, [stage, preview])

  return { dudeRef, shadowRef, canvasRef }
}
