import type { Stage } from '../../types'

/**
 * AgentRoom 行为剧本（行为队列状态机的数据源）。
 *
 * 一个「行为」= 目标工位 x + 到达后停留时执行的动作 + 停留时长。
 * useAgentPosition 逐个消费行为：先走到 x（rAF 插值），到位后执行 action 停留 ms，
 * 然后取下一个；队列空则按 stage 续排（工作 stage 循环剧本 / idle 随机续排）。
 *
 * 红线：这里只描述「stage 内部怎么演」，stage 本身只来自真实 RunEvent，不在此编造。
 */

// 工位横向位置（百分比，与画布宽度相除）。沿用原 STAGE_X 坐标基准，与家具带对齐。
export const STATION = {
  desk: 15, // 电脑桌（writing/checking/read）
  coffee: 26, // 咖啡角
  link: 46, // 连线台（linking 比划）
  cabinet: 76, // 档案柜（searching 翻找）
  home: 16, // idle 起始/歇脚点
} as const

// 各 stage 的静止/初始位置（12 个，供初值、预览、无脚本 stage 的歇脚点用）。
export const STAGE_HOME: Record<Stage, number> = {
  idle: STATION.home,
  uploading: 50,
  parsing: 50,
  extracting: 50,
  linking: STATION.link,
  indexing: 74,
  searching: STATION.cabinet,
  checking: STATION.desk,
  writing: STATION.desk,
  deleting: 86,
  rebuilding: 86,
  error: 50,
}

// 小人当前微动作：驱动 data-action，CSS 据此渲染姿态与道具（走/搬/读/打字/发呆/瞌睡…）。
export type AgentAction =
  | 'idle-breathe'
  | 'walk'
  | 'carry' // 搬文件走（走 + 手持文件）
  | 'take-cup' // 咖啡角取杯
  | 'drink' // 咖啡角喝咖啡
  | 'daze' // 原地发呆
  | 'doze' // 打瞌睡（zzz 气泡）
  | 'rummage' // 档案柜前翻找（放大镜）
  | 'read' // 桌前翻阅（手持文件）
  | 'gesture' // 连线台前比划（连线生长）
  | 'flip' // 桌前翻页核对（手持文件）
  | 'type' // 桌前打字
  | 'scratch' // 挠头
  | 'stretch' // 伸懒腰

// 一个行为。carrying：走向 x 的途中是否手持文件（searching 抱文件走回桌）。
export interface Behavior {
  x: number
  action: AgentAction
  ms: number
  carrying?: boolean
}

// 工作 stage 的循环剧本（循环直到 stage 变化）。只有 searching/linking/checking/writing
// 是 AgentRoom 真实可达的工作 stage（其余文档处理 stage 只在文档库订阅，从不到达本组件）。
const WORK_SCRIPTS: Partial<Record<Stage, Behavior[]>> = {
  // 档案柜前翻找 → 抱文件走回桌 → 桌前翻阅 → 循环
  searching: [
    { x: STATION.cabinet, action: 'rummage', ms: 1500 },
    { x: STATION.desk, action: 'read', ms: 1500, carrying: true },
  ],
  // 连线台前比划连线（基本驻留）
  linking: [{ x: STATION.link, action: 'gesture', ms: 2000 }],
  // 桌前翻页核对
  checking: [{ x: STATION.desk, action: 'flip', ms: 1800 }],
  // 桌前打字，偶尔挠头 / 伸懒腰
  writing: [
    { x: STATION.desk, action: 'type', ms: 2600 },
    { x: STATION.desk, action: 'scratch', ms: 900 },
    { x: STATION.desk, action: 'type', ms: 3000 },
    { x: STATION.desk, action: 'stretch', ms: 1100 },
  ],
}

// 取某 stage 的一轮工作剧本（深拷贝，避免调用方 mutate 常量）。null = 无循环剧本。
export function workScript(stage: Stage): Behavior[] | null {
  const s = WORK_SCRIPTS[stage]
  return s ? s.map((b) => ({ ...b })) : null
}

type IdleKind = 'daze' | 'wander' | 'drink' | 'doze'

// idle 加权随机候选：行为数据本体在 idleScript() 中展开成多段短剧本。
const IDLE_CHOICES: { kind: IdleKind; weight: number }[] = [
  { kind: 'daze', weight: 3 }, // 原地发呆
  { kind: 'wander', weight: 3 }, // 房间内踱步
  { kind: 'drink', weight: 2 }, // 走到咖啡角取杯并喝一口
  { kind: 'doze', weight: 1 }, // 打瞌睡
]

// idle 剧本：把一个空闲选择展开成 1~3 段行为，保留「中断即转」的可打断性。
function idleScript(kind: IdleKind, rng: () => number): Behavior[] {
  if (kind === 'drink') {
    return [
      { x: STATION.coffee, action: 'take-cup', ms: 700 },
      { x: STATION.coffee, action: 'drink', ms: 2200 },
      { x: STATION.home, action: 'idle-breathe', ms: 1200 },
    ]
  }
  if (kind === 'doze') {
    return [{ x: STATION.desk, action: 'doze', ms: 5000 }]
  }
  if (kind === 'daze') {
    return [{ x: STATION.home, action: 'daze', ms: 5000 }]
  }
  return [{ x: 12 + Math.floor(rng() * 70), action: 'idle-breathe', ms: 4000 }]
}

// idle：加权随机取下一段空闲剧本。
export function nextIdleScript(rng: () => number): Behavior[] {
  const total = IDLE_CHOICES.reduce((sum, c) => sum + c.weight, 0)
  let r = rng() * total
  let chosen = IDLE_CHOICES[0]
  for (const c of IDLE_CHOICES) {
    r -= c.weight
    if (r <= 0) {
      chosen = c
      break
    }
  }
  return idleScript(chosen.kind, rng)
}

// StyleGallery 预览：某 stage 的静态首帧行为（不循环）。有工作剧本用其首帧，否则在
// 该 stage 的歇脚位静立呼吸。ms 给极大值表示不推进（预览是静态展示）。
export function previewBehavior(stage: Stage): Behavior {
  const s = WORK_SCRIPTS[stage]
  if (s && s.length > 0) return { ...s[0], ms: Number.MAX_SAFE_INTEGER }
  return { x: STAGE_HOME[stage], action: 'idle-breathe', ms: Number.MAX_SAFE_INTEGER }
}
