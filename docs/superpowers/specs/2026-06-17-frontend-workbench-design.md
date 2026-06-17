# 前端工作台设计规格

日期：2026-06-17
状态：已确认（brainstorming 阶段产出）
作用域：graphrag-kg-agent 前端。本窗口交付 = **设计规格文档 + 指导文件 + Vite/React/TS 工程脚手架**，不实现完整页面。

> 本文是前端设计的正式落档，作为后续实现（writing-plans → 编码）的依据。本文不冻结前后端 API 契约——后端业务接口尚未实现，契约由后端就绪后协商收敛；本文以"前端需要什么数据"的视角列出需求清单作为对齐输入。

---

## 1. 目标与交付边界

### 目标

为 graphrag-kg-agent 产出一套高质量的前端**设计规格 + 指导文件**，外加一个干净的 **Vite + React + TS 工程脚手架**，让后续实现照着落地，不必反复争论 UI 边界。

### 本窗口做什么

- 信息架构与导航设计
- 组件树与各组件的数据需求清单（前端视角，非冻结契约）
- 视觉设计系统（配色 / 排版 / 间距 / 圆角 / 设计 token）
- 像素 Agent 造型与动画状态机规范
- Vite + React + TS 工程脚手架（目录 / 依赖 / 配置 / 设计 token / 带类型的占位组件）
- 两份指导文件 + 前端 DEVLOG 学习记录

### 本窗口不做什么

- 完整页面实现（各视图/组件为带 props 类型的占位实现）
- Mock 数据编排
- 接真实业务 API（后端尚无 documents / chat / runs / graph 接口）

### 唯一能接真后端的点

设置页的依赖健康状态可对接已有的 `GET /health`、`GET /health/deps`。此项作为脚手架预留，不在本窗口强求实现。

### 现状约束（决定上述边界的原因）

后端目前只有 `/health`、`/health/deps`、统一错误结构 `{"error": {"type", "message"}}`、配置加载与 Neo4j/LLM 客户端薄封装。业务接口与 `RunEvent` 数据均未实现，无真实数据可接——因此前端"做到底"的边界落在设计文档 + 脚手架，避免对着未冻结契约做无用功。

---

## 2. 信息架构与导航

整个前端是**单页应用（SPA）**，顶部一条全局导航栏 + 三个主视图（对应布局方案 D：主工作台沉浸 + 文档库/图谱独立视图）。

### 顶部全局栏（常驻）

```
[● GraphRAG 工作台]   问答 · 文档库 · 图谱          [Neo4j ●] [LLM ●] [⚙ 设置]
```

- 左：项目标识
- 中：三个主视图 tab
- 右：依赖状态灯（接 `/health/deps`）+ 设置入口
- 全局栏含一个**迷你 Run 状态指示**：当任意视图触发的操作产生后台 Run 时点亮，点击跳回问答工作台查看像素小人与事件流

### 三个主视图

1. **问答工作台**（默认主视图，布局 A）
   - 左主区：问答对话流 + 答案下方的引用证据区（可展开看原文 chunk）
   - 右栏上：像素 Agent 舞台（管理员工作间）
   - 右栏下：运行事件时间线（RunEvent 流，做小人动作的旁白）

2. **文档库**（独立视图，需要大空间）
   - 文档列表（来源 / 类型 / 解析状态 / 索引状态）
   - 上传 / 导入入口
   - 单文档详情（chunk 预览、删除、重建索引）

3. **图谱探索**（独立视图，全屏画布）
   - Cytoscape.js 图谱画布 + 实体搜索 + 邻域展开 + 选中实体看证据

### 设置页（从 ⚙ 进，抽屉或独立页）

模型配置提示、Neo4j/LLM 连通状态、样本导入说明。

### 贯穿性约束

像素小人和事件时间线只在问答工作台常驻，但文档入库/删除/重建（发生在文档库视图）也会产生 RunEvent。全局栏的迷你 Run 状态指示保证：无论操作在哪个视图触发，"动画来自真实 RunEvent"始终成立。

---

## 3. 问答工作台：组件分解与数据需求

按"单一职责、可独立理解"拆分。每个单元标出它需要的数据（前端视角需求，非冻结契约）。

### 布局骨架

```
WorkbenchView
├── 左主区 (flex 1.7)
│   ├── ChatThread        ── 对话消息列表（用户问 / Agent 答）
│   │   └── AnswerCard    ── 单条答案：正文 + 置信提示 + 引用角标
│   ├── CitationPanel     ── 引用证据区：点答案角标 → 展开对应 chunk 原文
│   └── ChatComposer      ── 底部输入框 + 发送
└── 右栏 (flex 1)
    ├── PixelAgentStage   ── 像素管理员工作间（见 §4）
    └── RunEventTimeline  ── RunEvent 流，时间倒序，高亮当前阶段
```

### 各单元数据需求清单

| 组件 | 需要的数据 | 用途 |
|---|---|---|
| `ChatThread/AnswerCard` | 答案正文、置信度提示、引用列表（每条含 chunk_id + 在答案中的位置/角标号） | 渲染带引用角标的答案 |
| `CitationPanel` | 按 chunk_id 取：原文片段、来源文档名、文档内位置 | 点角标展开原文，命中"引用可追溯"硬要求 |
| `RunEventTimeline` | RunEvent 流：每个事件含 `stage`、`status`、`message`、时间戳 | 渲染时间线 + 驱动小人动作 |
| `PixelAgentStage` | 当前 `stage`（从最新 RunEvent 派生） | 切换小人动作 |

### 两个关键设计点

1. **引用是一等公民**：`AnswerCard` 的引用角标与 `CitationPanel` 双向联动——点角标高亮原文，点原文反查答案中的引用处。这是项目护城河（可追溯），不可弱化。

2. **事件流与小人共享同一数据源**：`RunEventTimeline` 与 `PixelAgentStage` 消费同一条 RunEvent 流（脚手架设计成一个 `useRunEvents` 数据钩子，未来接 SSE `/api/runs/{id}/events/stream`，现在留接口）。保证"小人动作 = 真实事件"，二者永不脱节。

### 脚手架阶段落地

这些组件建成带 TypeScript 类型定义的空壳组件（props 类型 = 上面的数据需求），配 `RunEvent` / `Answer` / `Citation` 等的 `types.ts`。数据钩子先返回空/占位，等后端契约就绪再填实现。

---

## 4. 像素 Agent 动画状态机

项目的灵魂，硬规则最集中处。

### 核心原则（不可破）

小人的动作**完全由 RunEvent 派生的 `stage` 驱动**，前端绝不主动编造状态。单向数据流：

```
后端 RunEvent → useRunEvents 钩子 → 当前 stage → PixelAgentStage 切换动作
```

### 造型

拟人**档案管理员**（戴眼镜的研究员形象），往高级精致方向做。整体浅色专业基调中，小人区域用像素美学形成"反差萌"。

### 12 个状态

每个 stage = 管理员的一个拟物动作 + 工作间场景元素。

| stage | 管理员动作 | 场景元素 |
|---|---|---|
| `idle` | 待命，偶尔眨眼/翻书 | 安静的工作间 |
| `uploading` | 搬运文档进门 | 门口/收件筐 |
| `parsing` | 蹲下拆开文件包 | 拆包台 |
| `extracting` | 往纸上贴实体标签 | 标签贴纸 |
| `linking` | 拉关系线连接卡片 | 连线板 |
| `indexing` | 把文件归进档案柜 | 档案柜抽屉 |
| `searching` | 在文件堆里翻找 | 文件堆 |
| `checking` | 拿放大镜校对引用 | 放大镜 + 文档 |
| `writing` | 在打字机/键盘上打字 | 打字机 |
| `deleting` | 把文件塞进碎纸机 | 碎纸机 |
| `rebuilding` | 复印并重排文件 | 复印机 |
| `error` | 看错误纸条挠头 | 红色纸条 |

### 动画实现规范（CSS 分层方案）

- 小人拆成图层：`头`（含眼镜、表情）、`身体`、`左手`、`右手`、`道具`。每个图层是定位好的元素。
- 每个 stage = 一组 CSS `@keyframes`（手臂摆动、头部点动、道具进出场），配 `idle` 常驻呼吸动画作底。
- 状态切换有**短转场**（淡入淡出或小人转身），避免动作硬跳。
- 道具/场景元素按 stage 显隐（如只有 `deleting` 时碎纸机才亮起）。
- 不引入逐帧 sprite sheet（方案 A）或 Lottie/Rive（方案 C）。逐帧作为后续有余力的升级方向。

### 状态机健壮性

- 一段 Run 可能快速经过多个 stage——设计**最短停留时间**，防止动作闪烁。事件来得太快时排队播放，但**只平滑/排队已发生的真实事件，绝不伪造未发生的事件**。
- RunEvent 断流/结束 → 回落到 `idle`。
- 收到 `error` 事件 → 切错误动作并定格，直到下一个有效事件。

### 脚手架阶段落地

- 建 `PixelAgent/` 组件目录：`PixelAgent.tsx`（图层结构）、`animations.css`（12 套 keyframes 占位，至少 `idle` 做出可见效果作为样板）、`stageMap.ts`（stage → 动作配置映射表）。
- 配一个**本地开发调试开关**：能手动切 stage 预览 12 个动作。这只是开发预览工具，不是生产里的"伪造状态"——生产严格只认 RunEvent。

---

## 5. 工程脚手架结构与设计系统

### 技术选型（对齐规划）

- Vite + React + TS
- 普通 CSS Modules + CSS 变量（设计 token），不引 Tailwind（规范"优先简单稳定"，CSS 变量足够撑起浅色设计系统）
- Cytoscape.js（图谱，脚手架先装依赖不实现）

### 目录结构

```
frontend/
├── package.json / vite.config.ts / tsconfig.json
├── index.html
├── src/
│   ├── main.tsx / App.tsx          # 入口 + 路由（顶部 tab）
│   ├── styles/
│   │   ├── tokens.css              # 设计 token：配色/间距/圆角/字号
│   │   └── global.css
│   ├── types/                      # 数据契约类型（前端需求版，非冻结）
│   │   ├── runEvent.ts             # RunEvent / Stage 枚举
│   │   ├── answer.ts               # Answer / Citation
│   │   ├── document.ts
│   │   └── graph.ts
│   ├── hooks/
│   │   └── useRunEvents.ts         # 事件流钩子（占位，预留 SSE 接口）
│   ├── api/
│   │   └── client.ts               # fetch 封装 + 统一错误结构对接
│   ├── views/
│   │   ├── WorkbenchView/          # 问答工作台
│   │   ├── LibraryView/            # 文档库
│   │   ├── GraphView/              # 图谱探索
│   │   └── SettingsView/           # 设置（可接 /health/deps）
│   └── components/
│       ├── PixelAgent/             # 像素管理员（图层+keyframes+stageMap）
│       ├── ChatThread/
│       ├── ChatComposer/
│       ├── CitationPanel/
│       └── RunEventTimeline/
└── README.md                       # 前端启动说明
```

### 设计系统 token（浅色基调）

```css
--color-bg: #f7f8fa;          --color-surface: #ffffff;
--color-border: #e5e7eb;      --color-accent: #6366f1;       /* 靛紫 */
--color-accent-soft: #eef0ff; --color-text: #1f2937;
--color-text-muted: #6b7280;  --color-success / --color-error / ...
--radius: 8px;  --space-1 .. --space-6;
字体：系统无衬线（界面） + 等宽（chunk/代码）
```

像素小人区域用独立的像素字体 + `image-rendering: pixelated`，与外壳的现代无衬线形成"反差萌"。

### 脚手架完成度约定

- 工程能 `npm install && npm run dev` 起来，显示带顶部导航的空壳三视图 + 设置页。
- `types/` 写出完整 TS 类型（= 前端数据需求清单的代码化）。
- 设计 token、global 样式齐全；各视图/组件是带 props 类型的占位实现（结构在、内容是 placeholder）。
- **PixelAgent 例外**：至少把 `idle` 动作做出可见效果作为动画样板（证明 CSS 分层方案可行），其余 11 个 stage 留 keyframes 占位 + stageMap 配置。

### 交付的指导文件

1. **前端设计规格**（本文 `docs/superpowers/specs/2026-06-17-frontend-workbench-design.md`）
2. **像素 Agent 动画指南**（`frontend/docs/pixel-agent-guide.md`）：12 状态动作表、图层结构、加新状态的步骤、"动画必须来自真实 RunEvent"的红线。
3. **前端 DEVLOG 学习记录**（`frontend/DEVLOG.md`）：按项目约定，讲清 Vite/React/CSS Modules 等工具是什么、为什么这么选，面向初学者。

---

## 6. 硬规则对照检查

本设计对项目硬规则的遵守：

- **密钥与数据零提交**：前端不含任何密钥；模型配置仅在设置页"提示"，实际配置走后端 `.env`。
- **引用可追溯**：`AnswerCard` ↔ `CitationPanel` 双向联动，引用落到 chunk 原文，列为一等公民设计点。
- **像素动画来自真实 RunEvent**：单向数据流 + `useRunEvents` 单一数据源 + "只平滑不伪造"原则；开发预览开关明确隔离为非生产工具。
- **保留项目级控制权**：前端数据需求以清单形式提出，不冻结接口，等后端契约协商收敛。
- **简单优先**：CSS 变量而非 Tailwind；脚手架占位而非过度实现；不引重型动画方案。
