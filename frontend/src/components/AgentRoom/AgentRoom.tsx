import type { Stage } from '../../types'
import { sceneMap } from './sceneMap'
import { DUDE_SHADOW } from './drawDude'
import { useAgentPosition } from './useAgentPosition'
import styles from './AgentRoom.module.css'
import './roomScenes.css'

interface AgentRoomProps {
  stage: Stage
  // 外部 className 透传（用于父级控制 flex 比例等布局）。
  className?: string
}

/**
 * AgentRoom · 深紫调像素小房间（场景叙事版）。
 *
 * 定位：工作台才是主体，AgentRoom 是侧栏配角，动画只为反映程序正在执行什么。
 *
 * 机制：小人本体只悬浮（不做手臂逐帧），按 [data-stage] 横向飘移到对应家具工位前，
 * 动作由家具自身运转表达（打印机吐纸、咖啡冒热气、档案柜开抽屉、碎纸机吞纸）。
 *
 * 红线：stage 只来自真实 RunEvent（useRunEvents 守住），禁止前端编造。
 *
 * 道具/家具 DOM 常驻、CSS 按 data-stage 显隐（避免切换重建跳变）。
 * 道具用全局 class 名（p-xxx），不经 module hash，故 roomScenes.css 能稳定选中。
 */
export function AgentRoom({ stage, className }: AgentRoomProps) {
  const cfg = sceneMap[stage]
  const rootClass = [styles.room, className ?? ''].filter(Boolean).join(' ')
  // 小人位置由 rAF 逐帧插值驱动（中断即转），见 useAgentPosition.ts。
  // left 初值取本 stage 目标，避免首帧从默认值跳变。
  const { dudeRef, shadowRef } = useAgentPosition(stage)

  return (
    <div className={rootClass}>
      {/* 画布：承载所有场景元素，data-stage/data-busy 驱动 roomScenes.css */}
      <div className={styles.canvas} data-stage={stage} data-busy={cfg.busy}>
        {/* 门牌 */}
        <div className={styles.plate}>像素档案员</div>

        {/* 家具带（5 个工位，DOM 常驻，让小人有"家"）：
            电脑桌+显示器 ｜ 咖啡角 ｜ 打印机 ｜ 档案柜 ｜ 销毁台 */}
        <div className={styles.monitor} />
        <div className={styles.desk} />
        <div className={styles.coffee} />
        <div className={styles.steam}><i /><i /><i /></div>
        <div className={styles.printer} />
        <div className={styles.cabinet} />
        <div className={styles.shredder} />

        {/* 状态道具层：DOM 常驻，roomScenes.css 按 data-stage 显隐 + 驱动运转。
            全局 class 名（p-xxx，不经 hash），故直接写字符串。 */}
        <div className={styles.props}>
          {/* uploading：文档从右侧门飞向打印机 */}
          <div className="prop p-flydoc" />
          {/* parsing/extracting：打印机吐出的纸 */}
          <div className="prop p-paper" />
          <div className="prop p-paper p-paper2" />
          <div className="prop p-paper p-paper3" />
          {/* extracting：标签贴纸弹出 */}
          <div className="prop p-tag" />
          <div className="prop p-tag p-tag2" />
          {/* linking：两节点连线生长 */}
          <div className="prop p-link" />
          {/* indexing：档案柜绿光 */}
          <div className="prop p-cabglow" />
          {/* searching：放大镜 */}
          <div className="prop p-glass" />
          {/* deleting：碎纸机吞纸 + 碎屑 */}
          <div className="prop p-shredin" />
          <div className="prop p-shredout" />
        </div>

        {/* 小人：1 个 div + box-shadow 画全部像素（见 drawDude.ts）。
            left 由 useAgentPosition 的 rAF 插值驱动（中断即转），inline left 是初值。
            bottom 固定，bob 悬浮动画由 AgentRoom.module.css 负责。 */}
        <div className={styles.dudeShadow} ref={shadowRef} style={{ left: '16%' }} />
        <div
          className={styles.dude}
          ref={dudeRef}
          style={{ boxShadow: DUDE_SHADOW, left: '16%' }}
        />

        {/* error：红光（按 data-stage 显隐）*/}
        <div className={styles.pErr} />

        {/* 地面：像素条纹 + 扫描线 */}
        <div className={styles.ground} />
      </div>

      {/* 状态栏（画布下方，正常流）*/}
      <div className={styles.status}>
        <span className={styles.statusLabel}>{cfg.label}</span>
        <span className={styles.statusDetail}>{cfg.detail}</span>
      </div>
    </div>
  )
}
