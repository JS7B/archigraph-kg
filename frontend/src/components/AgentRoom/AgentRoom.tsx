import type { RunEvent, Stage } from '../../types'
import { sceneMap } from './sceneMap'
import { DUDE_SHADOW } from './drawDude'
import { useAgentPosition } from './useAgentPosition'
import { RunEventTimeline } from '../RunEventTimeline/RunEventTimeline'
import styles from './AgentRoom.module.css'
import './roomScenes.css'

interface AgentRoomProps {
  stage: Stage
  /** 运行事件流：驱动下方 RunEventTimeline（运行轨迹），由 useRunEvents 提供。 */
  events?: RunEvent[]
  /** 预览模式（StyleGallery）：只摆该 stage 剧本首帧的静态位置与动作，不循环演出。 */
  preview?: boolean
  // 外部 className 透传（用于父级控制 flex 比例等布局）。
  className?: string
}

/**
 * AgentRoom · 深紫调像素小房间（行为队列状态机版）。
 *
 * 定位：工作台才是主体，AgentRoom 是侧栏配角，演出只为反映程序正在执行什么。
 *
 * 机制：小人按当前 stage 的「行为剧本」在房间里演出——走到工位、翻找、抱文件、
 * 打字、发呆、瞌睡等，位置由 useAgentPosition 的 rAF 插值驱动（中断即转），
 * 微动作写在 canvas 的 data-action 上，roomScenes.css 据 [data-action] 渲染姿态与道具。
 * 环境动画（显示器、档案柜、咖啡热气、扫描线）由家具自身运转表达。
 *
 * 红线：stage 只来自真实 RunEvent（useRunEvents 守住），演出是 stage 内部的表现层
 * 编排；瞌睡/闲逛只在真实 idle 发生，不显示任何虚假阶段文案。
 *
 * 选择器机制：道具/小人的 stage/action 相关样式全部用 [data-stage]/[data-action]
 * 属性选择 + 全局类（ar-dude / p-xxx）命中，不依赖 CSS Module 哈希类名。
 */
export function AgentRoom({ stage, events, preview = false, className }: AgentRoomProps) {
  const cfg = sceneMap[stage]
  const rootClass = [styles.room, className ?? ''].filter(Boolean).join(' ')
  // 小人位置与微动作由行为队列状态机驱动（中断即转），见 useAgentPosition.ts。
  const { dudeRef, shadowRef, canvasRef } = useAgentPosition(stage, preview)

  return (
    <div className={rootClass}>
      {/* 画布：承载所有场景元素。data-stage/data-busy 由 React 控（真实 stage），
          data-action 由 useAgentPosition 直接写 DOM（微动作，不进 React 渲染）。 */}
      <div className={styles.canvas} ref={canvasRef} data-stage={stage} data-busy={cfg.busy}>
        {/* 门牌 */}
        <div className={styles.plate}>像素档案员</div>

        {/* 家具带（5 个工位，DOM 常驻，让小人有"家"）：
            电脑桌+显示器 ｜ 咖啡角 ｜ 打印机 ｜ 档案柜 ｜ 销毁台 */}
        <div className={styles.monitor} />
        <div className={styles.desk} />
        <div className={`${styles.coffee} coffee-station`} />
        <div className={`${styles.steam} p-steam`}><i /><i /><i /></div>
        <div className={styles.printer} />
        <div className={styles.cabinet} />
        <div className={styles.shredder} />

        {/* 状态道具层：DOM 常驻，roomScenes.css 按 [data-action] 显隐 + 驱动运转。
            全局 class 名（p-xxx，不经 hash）。
            - p-link：linking 的 gesture 动作时连线生长
            - p-glass：searching 的 rummage 动作时放大镜扫描 */}
        <div className={styles.props}>
          <div className="prop p-link" />
          <div className="prop p-glass" />
        </div>

        {/* 小人：1 个 div + box-shadow 画全部像素（见 drawDude.ts）。
            ar-dude 是稳定全局类，供 roomScenes.css 的 [data-action] 姿态动画命中
            （CSS Module 哈希类名无法被全局文件选中）。
            left 初值与逐帧位置由 useAgentPosition 写入；bottom 固定，bob 由 module CSS 管。
            手持文件 / zzz 气泡作为小人子元素，随小人移动，按 data-action 显隐。 */}
        <div className={styles.dudeShadow} ref={shadowRef} />
        <div
          className={`${styles.dude} ar-dude`}
          ref={dudeRef}
          style={{ boxShadow: DUDE_SHADOW }}
        >
          <span className="p-cup" />
          <span className="p-doc" />
          <span className="p-zzz">z</span>
        </div>

        {/* error：红光（按 [data-stage=error] 显隐，全局类 ar-err 命中）*/}
        <div className={`${styles.pErr} ar-err`} />

        {/* 地面：像素条纹 + 扫描线 */}
        <div className={styles.ground} />
      </div>

      {/* 运行轨迹（画布下方）：RunEventTimeline 复用现有组件。 */}
      <div className={styles.timeline}>
        <RunEventTimeline events={events ?? []} />
      </div>
    </div>
  )
}
