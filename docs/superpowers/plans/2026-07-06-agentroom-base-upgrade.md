# AgentRoom Base Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把前端 `AgentRoom` 升级成更完整的像素小工程师基地：重画小人、强化咖啡交互、提升打瞌睡可读性，并同步做房间与说明文档升级。

**Architecture:** 保留现有 `RunEvent -> Stage -> useAgentPosition -> AgentRoom` 链路，只改表现层。造型变化集中在 `drawDude.ts` 的像素稿与 `roomScenes.css` / `AgentRoom.module.css` 的动作和场景，道具编排集中在 `behaviors.ts`，文档同步更新。

**Tech Stack:** React · TypeScript · CSS Modules · 全局 CSS 动画 · box-shadow pixel art

---

### Task 1: 重画像素小工程师并引入可切换五官

**Files:**
- Modify: `frontend/src/components/AgentRoom/drawDude.ts`
- Modify: `frontend/src/styles/tokens.css`
- Test: `frontend/src/views/StyleGallery/StyleGallery.tsx`

- [ ] **Step 1: 先写失败标准（人工验收基线）**

在本地记下这 4 条人工验收基线，后续每次预览都对照：

```text
1. 常态能看出眼镜和眼睛，不再只有抽象色块。
2. doze 状态时，不看 zzz 也能看出困。
3. 嘴部能在 doze 状态显示小圆口。
4. 小人整体更像“机灵的小工程师”，不是单纯暖色人形。
```

- [ ] **Step 2: 预览当前版本，确认基线确实未满足**

Run: `cd frontend && npm run dev`

Expected: `StyleGallery` 或工作台里的当前小人仍然主要依赖姿态和 `zzz`，五官辨识度不足。

- [ ] **Step 3: 最小实现重画像素稿**

修改 `frontend/src/components/AgentRoom/drawDude.ts`：

```ts
const COLOR: Record<string, string> = {
  h: 'var(--dude-hair)',
  s: 'var(--dude-skin)',
  e: 'var(--dude-eye)',
  g: 'var(--dude-glass)',
  b: 'var(--dude-body)',
  B: 'var(--dude-body-hi)',
  d: 'var(--dude-body-lo)',
  l: 'var(--dude-leg)',
  m: 'var(--dude-mouth)',
}

const PATTERN: string[] = [
  '..hhh...',
  '.hhhhh..',
  '.hssss..',
  '.geseg..',
  '.ssmss..',
  '.dbBBb..',
  '.dbbbb..',
  '..ll.ll.',
]
```

说明：
- `geseg` 让眼镜和眼睛更明确。
- `m` 先进入常态图稿，后续由 CSS 状态控制其可见感。
- 头部横向多一格，增强头身比和人物感。

- [ ] **Step 4: 为嘴部颜色补 token 映射**

如果 `tokens.css` 尚无嘴部色，补一个温和深色变量，并在房间 token 区域统一定义：

```css
--dude-mouth: #6b3f2b;
```

位置：`frontend/src/styles/tokens.css` 里现有 `--dude-*` 变量附近。

- [ ] **Step 5: 运行预览确认造型通过第一轮**

Run: `cd frontend && npm run build`

Expected: build 通过；预览中常态能看出眼镜、眼睛、嘴部位置，小人剪影更像工程师助手。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AgentRoom/drawDude.ts frontend/src/styles/tokens.css
git commit -m "feat(frontend): redraw pixel engineer silhouette"
```

---

### Task 2: 升级咖啡交互剧本与随身杯道具

**Files:**
- Modify: `frontend/src/components/AgentRoom/behaviors.ts`
- Modify: `frontend/src/components/AgentRoom/AgentRoom.tsx`
- Modify: `frontend/src/components/AgentRoom/roomScenes.css`
- Modify: `frontend/src/components/AgentRoom/useAgentPosition.ts`

**Implementation Notes:**
- 当前 idle 机制只返回单段 `Behavior`；`drink` 要做成“取杯 -> 喝 -> 停顿”，必须同步小幅扩展 `useAgentPosition.ts` 的队列消费逻辑，不能只改 CSS。
- 计划中的 `.coffee-station` / `.p-steam` 是示意名，不是现有真实选择器。实施时应在 `AgentRoom.tsx` 给咖啡角/蒸汽节点补稳定类名或 `data-*` 属性，再由 `roomScenes.css` 命中；不要硬套示例类名。

- [ ] **Step 1: 写出咖啡交互的失败标准**

```text
当前 drink 失败标准：
- 只是在咖啡角附近停留
- 看不出“取杯”
- 看不出“喝”
- 咖啡角没有被触发
```

- [ ] **Step 2: 用现有实现验证它确实失败**

Run: `cd frontend && npm run dev`

Expected: 现有 `drink` 只有单一站位姿态，没有完整交互链。

- [ ] **Step 3: 把 drink 拆成短剧本**

修改 `frontend/src/components/AgentRoom/behaviors.ts` 的 `IDLE_CHOICES` 和 `nextIdleBehavior` 所依赖的数据结构，新增“取杯后喝”的分段支持。最小方案：

```ts
export type AgentAction =
  | 'idle-breathe'
  | 'walk'
  | 'carry'
  | 'take-cup'
  | 'drink'
  | 'daze'
  | 'doze'
  | 'rummage'
  | 'read'
  | 'gesture'
  | 'flip'
  | 'type'
  | 'scratch'
  | 'stretch'

export function idleScript(kind: 'drink' | 'daze' | 'doze' | 'wander', rng: () => number): Behavior[] {
  if (kind === 'drink') {
    return [
      { x: STATION.coffee, action: 'take-cup', ms: 700 },
      { x: STATION.coffee, action: 'drink', ms: 2200, carrying: true },
      { x: STATION.home, action: 'idle-breathe', ms: 1200 },
    ]
  }
  if (kind === 'doze') return [{ x: STATION.desk, action: 'doze', ms: 5000 }]
  if (kind === 'daze') return [{ x: STATION.home, action: 'daze', ms: 5000 }]
  return [{ x: 12 + Math.floor(rng() * 70), action: 'idle-breathe', ms: 4000 }]
}
```

说明：如果当前状态机不直接支持“返回多段 idle 行为”，就在 `frontend/src/components/AgentRoom/useAgentPosition.ts` 里按现有工作剧本模式消费该数组，不要重写整体架构。

- [ ] **Step 4: 给小人挂杯子道具**

在 `frontend/src/components/AgentRoom/AgentRoom.tsx` 的小人内部新增杯子节点：

```tsx
<span className="p-cup" />
```

放在 `p-doc` 与 `p-zzz` 之间，作为随身道具之一。

- [ ] **Step 5: 给 take-cup / drink 添加明确视觉**

在 `frontend/src/components/AgentRoom/roomScenes.css` 增加：

```css
.p-cup {
  position: absolute;
  left: 17px;
  bottom: 4px;
  width: 7px;
  height: 7px;
  background: var(--room-amber);
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 1px 1px 2px 2px;
  opacity: 0;
}

.p-cup::after {
  content: '';
  position: absolute;
  right: -3px;
  top: 1px;
  width: 2px;
  height: 3px;
  border: 1px solid rgba(255,255,255,0.4);
  border-left: none;
  border-radius: 0 2px 2px 0;
}

[data-action='take-cup'] .p-cup,
[data-action='drink'] .p-cup {
  opacity: 1;
}

[data-action='take-cup'] .ar-dude {
  animation: ar-take-cup 0.7s ease-out infinite;
}

[data-action='drink'] .ar-dude {
  animation: ar-drink 2.2s ease-in-out infinite;
}

@keyframes ar-take-cup {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-1px) rotate(-8deg); }
}
```

- [ ] **Step 6: 让咖啡角本体有被触发感**

在同一文件增加：

```css
[data-action='take-cup'] .coffee-steam,
[data-action='drink'] .coffee-steam,
[data-action='take-cup'] .coffee-node,
[data-action='drink'] .coffee-node {
  filter: brightness(1.12);
}
```

这里的 `coffee-node` / `coffee-steam` 仍然只是建议命名。若现有 DOM 尚无稳定选择器，先在 `AgentRoom.tsx` 补全局类名或 `data-prop="coffee"` / `data-prop="steam"` 之类的稳定钩子，再由 `roomScenes.css` 使用它们；不要直接依赖 CSS Module 哈希类名。

- [ ] **Step 7: 验证咖啡互动已可读**

Run: `cd frontend && npm run build`

Expected: `drink` 剧本能看出“取杯 -> 喝 -> 停顿”；被触发的是“小人和咖啡的关系”，不是单独乱动的咖啡机。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/AgentRoom/behaviors.ts frontend/src/components/AgentRoom/AgentRoom.tsx frontend/src/components/AgentRoom/roomScenes.css
git commit -m "feat(frontend): add explicit coffee interaction sequence"
```

---

### Task 3: 提升 doze 可读性并加入呼吸感

**Files:**
- Modify: `frontend/src/components/AgentRoom/AgentRoom.tsx`
- Modify: `frontend/src/components/AgentRoom/roomScenes.css`

- [ ] **Step 1: 写失败标准**

```text
当前 doze 的失败标准：
- 主要靠 zzz 才能理解
- 眼睛没有明显闭合感
- 嘴部没有呼吸感
```

- [ ] **Step 2: 预览确认当前失败**

Run: `cd frontend && npm run dev`

Expected: 仅靠姿态和 `zzz`，doze 的困倦表达仍不够直观。

- [ ] **Step 3: 在小人内部补“状态五官层”**

在 `frontend/src/components/AgentRoom/AgentRoom.tsx` 的小人内部新增：

```tsx
<span className="p-face p-face--doze" />
```

目的：不强行用 `box-shadow` 动态改写整张脸，而是用覆盖层在 `doze` 时提供闭眼和圆口。

- [ ] **Step 4: 用 doze 覆盖层表达闭眼与圆口**

在 `frontend/src/components/AgentRoom/roomScenes.css` 中新增：

```css
.p-face--doze {
  position: absolute;
  left: 7px;
  top: 7px;
  width: 12px;
  height: 8px;
  opacity: 0;
}

.p-face--doze::before,
.p-face--doze::after {
  content: '';
  position: absolute;
  top: 0;
  width: 4px;
  height: 1px;
  background: var(--dude-eye);
}

.p-face--doze::before { left: 0; }
.p-face--doze::after { right: 0; }

.p-face--doze {
  box-shadow: 5px 5px 0 0 var(--dude-mouth);
}

[data-action='doze'] .p-face--doze {
  opacity: 1;
  animation: ar-doze-face 3.4s ease-in-out infinite;
}

@keyframes ar-doze-face {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.04, 0.92); }
}
```

说明：这里的 `box-shadow` 单点用于嘴部圆口，允许简单近似，不追求拟真。

- [ ] **Step 5: 调整 doze 姿态为“慢呼吸”**

将现有 `ar-doze` 动画改成更慢、更呼吸感明确的版本：

```css
@keyframes ar-doze {
  0%, 100% { transform: translateY(0) rotate(-10deg) scale(1); }
  50% { transform: translateY(-1px) rotate(-10deg) scale(1.02, 0.98); }
}
```

- [ ] **Step 6: 验证 doze 已可独立读懂**

Run: `cd frontend && npm run build`

Expected: 即使遮掉 `zzz` 想象，也能从闭眼和圆口读出打瞌睡状态。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/AgentRoom/AgentRoom.tsx frontend/src/components/AgentRoom/roomScenes.css
git commit -m "feat(frontend): improve doze readability with face overlay"
```

---

### Task 4: 升级房间为 Agent 小基地配色与层次

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/components/AgentRoom/AgentRoom.module.css`
- Modify: `frontend/src/components/AgentRoom/roomScenes.css`

- [ ] **Step 1: 写出配色目标**

```text
目标：
- 深靛 / 炭蓝做空间基底
- 青蓝做系统反馈
- 琥珀暖光做生活和聚焦
- 小人保持暖色主体，但和房间更融合
```

- [ ] **Step 2: 先确认当前房间的问题**

Run: `cd frontend && npm run dev`

Expected: 房间已有深色基底，但工位分层、暖光与系统反馈的分工还不够清楚。

- [ ] **Step 3: 调整 AgentRoom 相关 token**

在 `frontend/src/styles/tokens.css` 的房间变量附近统一成这组方向值：

```css
--room-bg-top: #201c33;
--room-bg-bottom: #13111f;
--room-panel: #2a243f;
--room-panel-hi: #342d4d;
--room-cyan: #63d4ff;
--room-cyan-soft: rgba(99, 212, 255, 0.18);
--room-amber: #f0b35e;
--room-amber-soft: rgba(240, 179, 94, 0.22);
--room-floor: #171426;
--dude-body: #f08a4b;
--dude-body-hi: #ffb17a;
--dude-body-lo: #b45f2f;
```

若文件中现有变量名略有不同，按现有命名体系对位修改，不额外造第二套 token。

- [ ] **Step 4: 给主工位、咖啡角、资料柜拉开层次**

在 `frontend/src/components/AgentRoom/AgentRoom.module.css` 中，把以下思路落实到实际类：

```css
.deskZone {
  box-shadow: 0 0 0 1px rgba(255,255,255,0.04), 0 10px 30px rgba(99, 212, 255, 0.08);
}

.coffeeZone {
  box-shadow: 0 0 18px var(--room-amber-soft);
}

.cabinetZone {
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05);
}
```

说明：按现有真实类名改，不要求强行新增 `deskZone` 等命名；关键是“主工位偏冷亮、咖啡角偏暖亮、资料柜偏稳重”。

- [ ] **Step 5: 控制整体动画数量**

在 `frontend/src/components/AgentRoom/roomScenes.css` 检查并保证：

```text
同一时刻只让 1 到 2 个关键元素明显动起来：
- 小人自己
- 当前工位被触发的道具
```

如果已有持续扫描线、蒸汽、屏幕光等动画过多，就把非关键动画的幅度调弱而不是全删。

- [ ] **Step 6: 验证房间气质成立**

Run: `cd frontend && npm run build`

Expected: 房间更像“Agent 小基地”，而不是纯复古游戏小屋或纯档案室。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/components/AgentRoom/AgentRoom.module.css frontend/src/components/AgentRoom/roomScenes.css
git commit -m "feat(frontend): restyle agent room as mixed workspace base"
```

---

### Task 5: 同步预览与文档，不留口头规格

**Files:**
- Modify: `frontend/src/views/StyleGallery/StyleGallery.tsx`
- Modify: `frontend/src/views/StyleGallery/StyleGallery.module.css`
- Modify: `frontend/前端说明.md`
- Modify: `frontend/DEVLOG.md`

- [ ] **Step 1: 更新 StyleGallery 的展示文案**

在 `frontend/src/views/StyleGallery/StyleGallery.tsx` 中，把与 `drink` / `doze` / 房间描述相关的文案更新为：

```ts
const stageNotes = {
  idle: '空闲时会在小基地里呼吸、发呆、巡游或补咖啡。',
  searching: '资料柜前翻找，再抱着文件回主工位。',
  drink: '走到咖啡角取杯，喝一口再回到待机节奏。',
  doze: '闭眼横线 + 小圆口呼吸，zzz 只作辅助提示。',
}
```

如果当前文件没有这个结构，就把等价说明写到最接近的预览描述区。

- [ ] **Step 2: 更新前端说明文档**

在 `frontend/前端说明.md` 的 AgentRoom 章节补这 4 点：

```md
- 小人重画为更机灵的像素小工程师，而非单纯色块小人。
- 咖啡角从“站位”升级为“取杯-喝-停顿”的短剧本。
- doze 改为姿态 + 闭眼线 + 圆口呼吸的复合表达。
- 房间升级为兼具档案感与开发工位感的 Agent 小基地。
```

- [ ] **Step 3: 追加 DEVLOG 学习记录**

在 `frontend/DEVLOG.md` 追加：

```md
## 2026-07-06 AgentRoom 小基地升级
- 做了什么：把像素小人升级成更机灵的小工程师，并重做咖啡交互、打瞌睡表情和房间层次。
- 这是什么：这是一次“表现层重构”——不动 RunEvent 和状态机主链路，只升级画面、动作和道具可读性。
- 为什么需要：原版更像抽象状态指示器，缺少人格和互动；尤其喝咖啡与打瞌睡的识别成本偏高。
- 为什么这么做：保留 box-shadow 像素法和真实事件红线，只在 drawDude / behaviors / roomScenes / AgentRoom.module.css 这条前端链路升级，风险最小。
- 踩了什么坑：如果只靠姿态，不靠五官覆盖层，doze 很难做到“一眼看懂”；如果只动画咖啡角、不让小人拿杯子，drink 还是会像站位。
```

- [ ] **Step 4: 运行最终验证**

Run: `cd frontend && npm run typecheck && npm run build`

Expected: 两个命令都通过；StyleGallery 与工作台都能看到更新后的角色与房间。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/StyleGallery frontend/前端说明.md frontend/DEVLOG.md
git commit -m "docs(frontend): document agent room base upgrade"
```

---

## Self-Review

**Spec coverage:**  
- 小人升级：Task 1 覆盖。  
- 咖啡交互：Task 2 覆盖。  
- doze 五官与呼吸：Task 3 覆盖。  
- 房间升级：Task 4 覆盖。  
- 文档与预览同步：Task 5 覆盖。  
- 后端不参与：全计划未触碰后端文件。  

**Placeholder scan:**  
- 无 `TODO` / `TBD`。  
- 每个任务都给了文件、代码或文本、命令和预期。  

**Type consistency:**  
- `take-cup` 在 Task 2 中已同步扩展 `AgentAction`。  
- `p-cup` / `p-face--doze` 都在 JSX 和 CSS 两侧成对出现。  
- 所有修改都落在现有 `AgentRoom` 相关前端链路内。  

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-agentroom-base-upgrade.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
