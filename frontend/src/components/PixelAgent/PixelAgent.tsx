import { useState } from 'react'
import type { Stage } from '../../types'
import { stageMap, ALL_STAGES } from './stageMap'
import styles from './PixelAgent.module.css'
import './animations.css'

interface PixelAgentProps {
  stage: Stage
  // 仅供开发预览：显示手动切 stage 的按钮。
  // 红线：这只是开发工具，生产中 stage 必须来自真实 RunEvent，禁止用它驱动生产状态。
  devControls?: boolean
}

export function PixelAgent({ stage, devControls = false }: PixelAgentProps) {
  const [previewStage, setPreviewStage] = useState<Stage | null>(null)
  const active = devControls && previewStage ? previewStage : stage
  const cfg = stageMap[active]

  return (
    <div className={styles.stage}>
      <div className={styles.scene}>{cfg.scene}</div>
      {/* 分层小人：头（含眼镜）/ 身体 / 左右手 / 道具。idle 有可见呼吸动画作样板。 */}
      <div className={`${styles.agent} ${cfg.animClass}`}>
        <div className={styles.head}>
          <div className={styles.glasses} />
        </div>
        <div className={styles.body} />
        <div className={styles.armLeft} />
        <div className={styles.armRight} />
        <div className={styles.prop} />
      </div>
      <div className={styles.label}>{cfg.label}</div>

      {devControls && (
        <div className={styles.devControls}>
          {ALL_STAGES.map((s) => (
            <button
              key={s}
              className={s === active ? styles.devBtnActive : styles.devBtn}
              onClick={() => setPreviewStage(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
