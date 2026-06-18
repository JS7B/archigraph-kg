# 前端工作台脚手架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 graphrag-kg-agent 前端的 Vite + React + TS 工程脚手架——带顶部导航的三视图 + 设置页空壳、完整数据类型、设计系统 token、像素管理员组件（idle 动作可见 + 其余 11 状态占位），以及两份指导文件。

**Architecture:** 单页应用（SPA），顶部全局栏 + 三主视图（问答工作台 / 文档库 / 图谱）+ 设置页。组件为带 props 类型的占位实现；`PixelAgent` 的 idle 动作做出可见效果作为 CSS 分层动画样板。数据钩子与 API 客户端留接口、返回占位，不接业务后端。

**Tech Stack:** Vite · React · TypeScript · CSS Modules + CSS 变量（设计 token）· Cytoscape.js（仅装依赖不实现）。Node 24 / npm 11。

> 实现注记（2026-06-17 执行后回填）：Vite 脚手架实际锁定 React 19.2 / Vite 8 / TypeScript 6（非计划初稿设想的 React 18，构建正常）。`src/vite-env.d.ts` 未单独创建——等价能力由 `tsconfig.app.json` 的 `types: ["vite/client"]` 全局提供。

## Global Constraints

- **本窗口不实现完整页面**：各视图/组件为带 props 类型的占位实现（结构在、内容是 placeholder）。
- **PixelAgent 例外**：至少把 `idle` 动作做出可见效果作为动画样板，其余 11 个 stage 留 keyframes 占位 + stageMap 配置。
- **像素动画状态必须来自真实 RunEvent**：单向数据流，前端绝不编造状态。开发预览开关明确隔离为非生产工具（注释标明）。
- **引用可追溯**：类型定义中 `Citation` 必须含 `chunkId` 等可回溯字段。
- **配置零硬编码密钥**：前端不含任何密钥；API base URL 走环境变量 `VITE_API_BASE_URL`。
- **不引 Tailwind**：用 CSS Modules + CSS 变量。
- **设计基调**：浅色，主色靛紫 `#6366f1`，背景 `#f7f8fa`，圆角 `8px`。
- **目录与命名**：严格按规格 §5 的目录结构。
- **工作目录**：worktree `E:\Mine\graphrag-kg-agent\.claude\worktrees\frontend-design`，分支 `feat/frontend`，所有命令在 `frontend/` 下执行（除 git）。
- **DEVLOG 约定**：前端板块的学习记录写进 `frontend/DEVLOG.md`，面向初学者讲清"是什么/为什么"。

---

### Task 1: 初始化 Vite + React + TS 工程与配置

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/.env.example`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/vite-env.d.ts`
- Delete: `frontend/.gitkeep`

**Interfaces:**
- Produces: 可 `npm run dev` / `npm run build` / `npm run typecheck` 的工程；`App` 默认导出（占位，后续 Task 5 替换为真正的 shell）。

- [ ] **Step 1: 用 Vite 脚手架生成基础工程**

在 `frontend/` 下执行（`.` 表示当前目录，需先删除占位文件避免冲突）：

```bash
cd frontend
rm -f .gitkeep
npm create vite@latest . -- --template react-ts
```

若交互式询问是否在非空目录继续，选择忽略并继续（目录里只有被删的 .gitkeep）。

- [ ] **Step 2: 安装依赖**

```bash
cd frontend
npm install
npm install cytoscape
npm install -D @types/cytoscape
```

- [ ] **Step 3: 在 package.json 增加 typecheck 脚本**

确认/修改 `frontend/package.json` 的 `scripts` 段包含：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit"
  }
}
```

- [ ] **Step 4: 创建前端环境变量示例**

创建 `frontend/.env.example`：

```
# 后端 API 地址（开发期默认本地 FastAPI）
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 5: 设置页面标题**

修改 `frontend/index.html`，将 `<title>` 改为：

```html
<title>GraphRAG 工作台</title>
```

- [ ] **Step 6: 验证工程可构建**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: typecheck 无错误；build 成功生成 `dist/`。

- [ ] **Step 7: 提交**

```bash
git add frontend/ -A
git commit -m "chore(frontend): 初始化 Vite + React + TS 工程与配置"
```

---

### Task 2: 设计系统 token 与全局样式

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`
- Modify: `frontend/src/main.tsx`（引入两个样式文件）
- Delete: `frontend/src/App.css`、`frontend/src/index.css`（Vite 模板自带，替换掉）

**Interfaces:**
- Produces: 全局可用的 CSS 变量（`--color-accent` 等），供后续所有组件的 CSS Modules 引用。

- [ ] **Step 1: 创建设计 token**

创建 `frontend/src/styles/tokens.css`：

```css
:root {
  /* 颜色 */
  --color-bg: #f7f8fa;
  --color-surface: #ffffff;
  --color-border: #e5e7eb;
  --color-accent: #6366f1;
  --color-accent-soft: #eef0ff;
  --color-accent-border: #c7d2fe;
  --color-text: #1f2937;
  --color-text-muted: #6b7280;
  --color-success: #16a34a;
  --color-error: #dc2626;
  --color-warning: #d97706;

  /* 间距 */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  /* 圆角 */
  --radius: 8px;
  --radius-sm: 4px;

  /* 字体 */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: "SF Mono", "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace;

  /* 字号 */
  --text-sm: 13px;
  --text-base: 14px;
  --text-lg: 16px;
  --text-xl: 20px;
}
```

- [ ] **Step 2: 创建全局样式**

创建 `frontend/src/styles/global.css`：

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body, #root {
  height: 100%;
}

body {
  font-family: var(--font-sans);
  font-size: var(--text-base);
  color: var(--color-text);
  background: var(--color-bg);
  -webkit-font-smoothing: antialiased;
}

button {
  font-family: inherit;
  cursor: pointer;
}

code, pre {
  font-family: var(--font-mono);
}
```

- [ ] **Step 3: 替换 main.tsx 的样式引入**

修改 `frontend/src/main.tsx`，移除 Vite 模板的 `import './index.css'`，改为：

```tsx
import './styles/tokens.css'
import './styles/global.css'
```

- [ ] **Step 4: 删除模板自带样式**

```bash
cd frontend
rm -f src/App.css src/index.css
```

确认 `src/App.tsx` 中若有 `import './App.css'` 则一并删除该行。

- [ ] **Step 5: 验证**

```bash
cd frontend
npm run typecheck
npm run dev
```

Expected: typecheck 通过；dev server 启动，页面背景为浅灰 `#f7f8fa`，无样式报错（控制台无 404）。

- [ ] **Step 6: 提交**

```bash
git add frontend/ -A
git commit -m "feat(frontend): 设计系统 token 与全局样式（浅色基调）"
```

---

### Task 3: 数据契约 TypeScript 类型

**Files:**
- Create: `frontend/src/types/runEvent.ts`
- Create: `frontend/src/types/answer.ts`
- Create: `frontend/src/types/document.ts`
- Create: `frontend/src/types/graph.ts`
- Create: `frontend/src/types/index.ts`

**Interfaces:**
- Produces: `Stage`、`RunEvent`、`Answer`、`Citation`、`DocumentMeta`、`GraphNode`、`GraphEdge` 等类型，供后续组件 props 引用。这是"前端数据需求清单"的代码化（非冻结契约）。

- [ ] **Step 1: 定义 Stage 与 RunEvent 类型**

创建 `frontend/src/types/runEvent.ts`：

```ts
// 像素 Agent 的 12 个工作状态。顺序与规格 §4 一致。
export type Stage =
  | 'idle'
  | 'uploading'
  | 'parsing'
  | 'extracting'
  | 'linking'
  | 'indexing'
  | 'searching'
  | 'checking'
  | 'writing'
  | 'deleting'
  | 'rebuilding'
  | 'error'

export type RunEventStatus = 'started' | 'progress' | 'done' | 'failed'

// 后端推送的单条运行事件（前端需求版，字段名待后端契约协商）。
export interface RunEvent {
  stage: Stage
  status: RunEventStatus
  message: string
  timestamp: number // 毫秒时间戳
}
```

- [ ] **Step 2: 定义 Answer 与 Citation 类型**

创建 `frontend/src/types/answer.ts`：

```ts
// 引用：必须能回到来源 chunk（引用可追溯硬要求）。
export interface Citation {
  index: number // 答案中的角标号，从 1 开始
  chunkId: string // 来源 chunk 标识，用于反查原文
  documentName: string // 来源文档名
  location: string // 文档内位置（如页码 / 段落，形态待后端定）
  snippet: string // 原文片段
}

export interface Answer {
  id: string
  text: string // 答案正文
  confidence: 'high' | 'medium' | 'low' // 置信提示
  citations: Citation[]
}

// 对话消息：用户提问或 Agent 回答。
export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  text: string
  answer?: Answer // role === 'agent' 时携带结构化答案
}
```

- [ ] **Step 3: 定义 Document 类型**

创建 `frontend/src/types/document.ts`：

```ts
export type DocumentSourceType = 'pdf' | 'markdown' | 'txt' | 'repo'
export type ParseStatus = 'pending' | 'parsing' | 'parsed' | 'failed'
export type IndexStatus = 'pending' | 'indexing' | 'indexed' | 'failed'

export interface DocumentMeta {
  id: string
  name: string
  sourceType: DocumentSourceType
  parseStatus: ParseStatus
  indexStatus: IndexStatus
  chunkCount: number
}
```

- [ ] **Step 4: 定义 Graph 类型**

创建 `frontend/src/types/graph.ts`：

```ts
export interface GraphNode {
  id: string
  label: string
  entityType: string // 实体类型（人物/机构/技术概念等，开发期收敛）
}

export interface GraphEdge {
  id: string
  source: string // 源节点 id
  target: string // 目标节点 id
  relationType: string // 业务关系类型（先统一 :RELATES，类型作属性）
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}
```

- [ ] **Step 5: 创建统一导出**

创建 `frontend/src/types/index.ts`：

```ts
export * from './runEvent'
export * from './answer'
export * from './document'
export * from './graph'
```

- [ ] **Step 6: 验证类型可编译**

```bash
cd frontend
npm run typecheck
```

Expected: 无类型错误。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/types/ -A
git commit -m "feat(frontend): 数据契约 TypeScript 类型（前端需求版）"
```

---

### Task 4: API 客户端与 useRunEvents 钩子（占位）

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useRunEvents.ts`

**Interfaces:**
- Consumes: `RunEvent`、`Stage`（Task 3）。
- Produces:
  - `apiFetch<T>(path: string, init?: RequestInit): Promise<T>` —— fetch 封装，解析统一错误结构。
  - `ApiError`（含 `type: string`、`message: string`）。
  - `useRunEvents(): { events: RunEvent[]; currentStage: Stage }` —— 事件流钩子，当前返回占位空流（currentStage 恒为 `'idle'`），预留 SSE 接入点。

- [ ] **Step 1: 创建 API 客户端**

创建 `frontend/src/api/client.ts`：

```ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// 对接后端统一错误结构 {"error": {"type", "message"}}。
export class ApiError extends Error {
  type: string
  constructor(type: string, message: string) {
    super(message)
    this.type = type
    this.name = 'ApiError'
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let type = 'http_error'
    let message = res.statusText
    try {
      const body = await res.json()
      if (body?.error) {
        type = body.error.type ?? type
        message = body.error.message ?? message
      }
    } catch {
      // 响应非 JSON，沿用 statusText
    }
    throw new ApiError(type, message)
  }
  return res.json() as Promise<T>
}
```

- [ ] **Step 2: 创建 useRunEvents 钩子（占位）**

创建 `frontend/src/hooks/useRunEvents.ts`：

```ts
import { useMemo } from 'react'
import type { RunEvent, Stage } from '../types'

// 运行事件流钩子。RunEventTimeline 与 PixelAgentStage 共享此唯一数据源，
// 保证"小人动作 = 真实事件"。
//
// 占位实现：当前返回空事件流。后端就绪后，这里改为订阅
// SSE  /api/runs/{runId}/events/stream，把收到的 RunEvent 累积进 events。
// 红线：currentStage 只能从真实 events 派生，禁止前端编造。
export function useRunEvents(): { events: RunEvent[]; currentStage: Stage } {
  const events: RunEvent[] = useMemo(() => [], [])
  const currentStage: Stage =
    events.length > 0 ? events[events.length - 1].stage : 'idle'
  return { events, currentStage }
}
```

- [ ] **Step 3: 验证**

```bash
cd frontend
npm run typecheck
```

Expected: 无类型错误。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/ frontend/src/hooks/ -A
git commit -m "feat(frontend): API 客户端与 useRunEvents 钩子（占位，预留 SSE）"
```

---

### Task 5: 应用外壳与顶部导航

**Files:**
- Create: `frontend/src/App.tsx`（覆盖 Task 1 的占位）
- Create: `frontend/src/App.module.css`
- Create: `frontend/src/components/TopBar/TopBar.tsx`
- Create: `frontend/src/components/TopBar/TopBar.module.css`

**Interfaces:**
- Consumes: 无（视图组件在 Task 6 创建，本任务先用内联占位 div，Task 6 替换）。
- Produces:
  - `type ViewKey = 'workbench' | 'library' | 'graph'`
  - `App` 默认导出：管理当前视图状态 + 渲染 TopBar + 视图区。
  - `TopBar` 组件：props `{ active: ViewKey; onChange: (v: ViewKey) => void; onOpenSettings: () => void }`。

- [ ] **Step 1: 创建 TopBar 组件**

创建 `frontend/src/components/TopBar/TopBar.tsx`：

```tsx
import styles from './TopBar.module.css'

export type ViewKey = 'workbench' | 'library' | 'graph'

const TABS: { key: ViewKey; label: string }[] = [
  { key: 'workbench', label: '问答' },
  { key: 'library', label: '文档库' },
  { key: 'graph', label: '图谱' },
]

interface TopBarProps {
  active: ViewKey
  onChange: (v: ViewKey) => void
  onOpenSettings: () => void
}

export function TopBar({ active, onChange, onOpenSettings }: TopBarProps) {
  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.dot} />
        GraphRAG 工作台
      </div>
      <nav className={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={t.key === active ? styles.tabActive : styles.tab}
            onClick={() => onChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className={styles.status}>
        {/* 依赖状态灯占位：后续接 /health/deps */}
        <span className={styles.depLabel}>Neo4j ●</span>
        <span className={styles.depLabel}>LLM ●</span>
        <button className={styles.settingsBtn} onClick={onOpenSettings}>
          ⚙ 设置
        </button>
      </div>
    </header>
  )
}
```

- [ ] **Step 2: 创建 TopBar 样式**

创建 `frontend/src/components/TopBar/TopBar.module.css`：

```css
.bar {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: 0 var(--space-4);
  height: 48px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 600;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent);
}

.tabs {
  display: flex;
  gap: var(--space-2);
}

.tab, .tabActive {
  border: none;
  background: transparent;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: var(--text-base);
}

.tabActive {
  color: var(--color-accent);
  background: var(--color-accent-soft);
  font-weight: 600;
}

.status {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.depLabel {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.settingsBtn {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--color-text);
}
```

- [ ] **Step 3: 创建 App 外壳**

创建/覆盖 `frontend/src/App.tsx`：

```tsx
import { useState } from 'react'
import { TopBar, type ViewKey } from './components/TopBar/TopBar'
import styles from './App.module.css'

export default function App() {
  const [view, setView] = useState<ViewKey>('workbench')
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <div className={styles.app}>
      <TopBar
        active={view}
        onChange={setView}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className={styles.main}>
        {view === 'workbench' && <div>问答工作台（占位）</div>}
        {view === 'library' && <div>文档库（占位）</div>}
        {view === 'graph' && <div>图谱探索（占位）</div>}
      </main>
      {settingsOpen && (
        <div className={styles.settingsPlaceholder}>
          设置（占位）
          <button onClick={() => setSettingsOpen(false)}>关闭</button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: 创建 App 样式**

创建 `frontend/src/App.module.css`：

```css
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.main {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
}

.settingsPlaceholder {
  position: fixed;
  top: 48px;
  right: 0;
  width: 320px;
  bottom: 0;
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
  padding: var(--space-4);
}
```

- [ ] **Step 5: 验证导航可切换**

```bash
cd frontend
npm run typecheck
npm run dev
```

Expected: 顶部出现导航栏；点击「问答/文档库/图谱」切换主区占位文字；点「⚙ 设置」右侧弹出设置占位面板，点关闭消失。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/ -A
git commit -m "feat(frontend): 应用外壳与顶部导航（三视图切换 + 设置入口）"
```

---

### Task 6: 三视图与设置页占位组件

**Files:**
- Create: `frontend/src/views/WorkbenchView/WorkbenchView.tsx`
- Create: `frontend/src/views/WorkbenchView/WorkbenchView.module.css`
- Create: `frontend/src/views/LibraryView/LibraryView.tsx`
- Create: `frontend/src/views/GraphView/GraphView.tsx`
- Create: `frontend/src/views/SettingsView/SettingsView.tsx`
- Modify: `frontend/src/App.tsx`（用真实视图组件替换内联占位）

**Interfaces:**
- Consumes: `App` 的视图切换（Task 5）。
- Produces:
  - `WorkbenchView` —— 布局 A 骨架：左主区 + 右栏（右栏含两个槽位，PixelAgent 与 Timeline 在 Task 7/8 填入）。
  - `LibraryView`、`GraphView`、`SettingsView` —— 占位组件，无 props。

- [ ] **Step 1: 创建 WorkbenchView 布局骨架**

创建 `frontend/src/views/WorkbenchView/WorkbenchView.tsx`：

```tsx
import styles from './WorkbenchView.module.css'

export function WorkbenchView() {
  return (
    <div className={styles.workbench}>
      <section className={styles.mainCol}>
        <div className={styles.chatThread}>问答对话流（占位）</div>
        <div className={styles.citation}>引用证据区（占位）</div>
        <div className={styles.composer}>输入框（占位）</div>
      </section>
      <aside className={styles.sideCol}>
        <div className={styles.stageSlot}>像素 Agent 舞台（占位）</div>
        <div className={styles.timelineSlot}>运行事件时间线（占位）</div>
      </aside>
    </div>
  )
}
```

- [ ] **Step 2: 创建 WorkbenchView 样式（布局 A 比例）**

创建 `frontend/src/views/WorkbenchView/WorkbenchView.module.css`：

```css
.workbench {
  display: flex;
  gap: var(--space-4);
  height: 100%;
}

.mainCol {
  flex: 1.7;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.chatThread {
  flex: 1;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-4);
}

.citation {
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-border);
  border-radius: var(--radius);
  padding: var(--space-3);
}

.composer {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-3);
}

.sideCol {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.stageSlot {
  flex: 1.2;
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-border);
  border-radius: var(--radius);
  padding: var(--space-3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.timelineSlot {
  flex: 1;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-3);
}
```

- [ ] **Step 3: 创建其余三个占位视图**

创建 `frontend/src/views/LibraryView/LibraryView.tsx`：

```tsx
export function LibraryView() {
  return <div>文档库：列表 / 上传导入 / 文档详情（占位）</div>
}
```

创建 `frontend/src/views/GraphView/GraphView.tsx`：

```tsx
export function GraphView() {
  return <div>图谱探索：Cytoscape.js 画布 / 实体搜索 / 邻域展开（占位）</div>
}
```

创建 `frontend/src/views/SettingsView/SettingsView.tsx`：

```tsx
export function SettingsView() {
  return (
    <div>
      设置：模型配置提示 / Neo4j · LLM 连通状态（可接 /health/deps）/
      样本导入说明（占位）
    </div>
  )
}
```

- [ ] **Step 4: 在 App 中接入真实视图**

修改 `frontend/src/App.tsx`，在文件顶部导入：

```tsx
import { WorkbenchView } from './views/WorkbenchView/WorkbenchView'
import { LibraryView } from './views/LibraryView/LibraryView'
import { GraphView } from './views/GraphView/GraphView'
import { SettingsView } from './views/SettingsView/SettingsView'
```

将 `<main>` 内的内联占位替换为：

```tsx
      <main className={styles.main}>
        {view === 'workbench' && <WorkbenchView />}
        {view === 'library' && <LibraryView />}
        {view === 'graph' && <GraphView />}
      </main>
```

将设置占位面板内容替换为 `SettingsView`：

```tsx
      {settingsOpen && (
        <div className={styles.settingsPlaceholder}>
          <SettingsView />
          <button onClick={() => setSettingsOpen(false)}>关闭</button>
        </div>
      )}
```

- [ ] **Step 5: 验证**

```bash
cd frontend
npm run typecheck
npm run dev
```

Expected: 切到「问答」显示左右分栏（左 1.7 / 右 1）布局，五个占位块清晰；其余视图与设置显示对应占位文字。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/ -A
git commit -m "feat(frontend): 三视图与设置页占位组件（含工作台布局 A 骨架）"
```

---

### Task 7: 工作台子组件占位（含引用联动接口）

**Files:**
- Create: `frontend/src/components/ChatThread/ChatThread.tsx`
- Create: `frontend/src/components/ChatComposer/ChatComposer.tsx`
- Create: `frontend/src/components/CitationPanel/CitationPanel.tsx`
- Create: `frontend/src/components/RunEventTimeline/RunEventTimeline.tsx`
- Create: `frontend/src/components/RunEventTimeline/RunEventTimeline.module.css`
- Modify: `frontend/src/views/WorkbenchView/WorkbenchView.tsx`（用真实子组件替换占位 div）

**Interfaces:**
- Consumes: `ChatMessage`、`Citation`（Task 3）；`RunEvent`（Task 3）；`useRunEvents`（Task 4）。
- Produces（props 类型 = 数据需求清单的代码化）：
  - `ChatThread` props `{ messages: ChatMessage[]; onCitationClick: (chunkId: string) => void }`
  - `ChatComposer` props `{ onSend: (text: string) => void }`
  - `CitationPanel` props `{ citations: Citation[]; activeChunkId: string | null }`
  - `RunEventTimeline` props `{ events: RunEvent[] }`

- [ ] **Step 1: 创建 ChatThread（占位 + 引用点击接口）**

创建 `frontend/src/components/ChatThread/ChatThread.tsx`：

```tsx
import type { ChatMessage } from '../../types'

interface ChatThreadProps {
  messages: ChatMessage[]
  onCitationClick: (chunkId: string) => void
}

// 占位：渲染消息列表；答案的引用角标点击回调已接通（引用可追溯硬要求）。
export function ChatThread({ messages, onCitationClick }: ChatThreadProps) {
  if (messages.length === 0) {
    return <div>提出第一个问题，开始与知识库对话（占位）</div>
  }
  return (
    <div>
      {messages.map((m) => (
        <div key={m.id}>
          <strong>{m.role === 'user' ? '你' : 'Agent'}：</strong>
          {m.text}
          {m.answer?.citations.map((c) => (
            <sup
              key={c.index}
              style={{ cursor: 'pointer', color: 'var(--color-accent)' }}
              onClick={() => onCitationClick(c.chunkId)}
            >
              [{c.index}]
            </sup>
          ))}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 创建 ChatComposer（占位）**

创建 `frontend/src/components/ChatComposer/ChatComposer.tsx`：

```tsx
import { useState } from 'react'

interface ChatComposerProps {
  onSend: (text: string) => void
}

export function ChatComposer({ onSend }: ChatComposerProps) {
  const [text, setText] = useState('')
  return (
    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
      <input
        style={{ flex: 1, padding: 'var(--space-2)' }}
        value={text}
        placeholder="向知识库提问…"
        onChange={(e) => setText(e.target.value)}
      />
      <button
        onClick={() => {
          if (text.trim()) {
            onSend(text)
            setText('')
          }
        }}
      >
        发送
      </button>
    </div>
  )
}
```

- [ ] **Step 3: 创建 CitationPanel（占位 + 高亮接口）**

创建 `frontend/src/components/CitationPanel/CitationPanel.tsx`：

```tsx
import type { Citation } from '../../types'

interface CitationPanelProps {
  citations: Citation[]
  activeChunkId: string | null
}

// 占位：展示引用原文；activeChunkId 命中的条目高亮（与 ChatThread 角标双向联动）。
export function CitationPanel({ citations, activeChunkId }: CitationPanelProps) {
  if (citations.length === 0) {
    return <div>引用证据将在回答生成后显示（占位）</div>
  }
  return (
    <div>
      {citations.map((c) => (
        <div
          key={c.index}
          style={{
            fontWeight: c.chunkId === activeChunkId ? 600 : 400,
          }}
        >
          [{c.index}] {c.documentName} · {c.location}：{c.snippet}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: 创建 RunEventTimeline（占位）**

创建 `frontend/src/components/RunEventTimeline/RunEventTimeline.tsx`：

```tsx
import type { RunEvent } from '../../types'
import styles from './RunEventTimeline.module.css'

interface RunEventTimelineProps {
  events: RunEvent[]
}

// 占位：时间倒序渲染事件，最新（当前阶段）高亮。与 PixelAgentStage 共享同一事件源。
export function RunEventTimeline({ events }: RunEventTimelineProps) {
  if (events.length === 0) {
    return <div className={styles.empty}>暂无运行事件（占位）</div>
  }
  return (
    <ul className={styles.list}>
      {[...events].reverse().map((e, i) => (
        <li key={e.timestamp} className={i === 0 ? styles.current : styles.item}>
          ▸ {e.stage} · {e.message}
        </li>
      ))}
    </ul>
  )
}
```

创建 `frontend/src/components/RunEventTimeline/RunEventTimeline.module.css`：

```css
.list {
  list-style: none;
  font-size: var(--text-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item {
  color: var(--color-text-muted);
}

.current {
  color: var(--color-accent);
  font-weight: 600;
}

.empty {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
```

- [ ] **Step 5: 在 WorkbenchView 接入子组件并连通引用联动**

覆盖 `frontend/src/views/WorkbenchView/WorkbenchView.tsx`：

```tsx
import { useState } from 'react'
import { ChatThread } from '../../components/ChatThread/ChatThread'
import { ChatComposer } from '../../components/ChatComposer/ChatComposer'
import { CitationPanel } from '../../components/CitationPanel/CitationPanel'
import { RunEventTimeline } from '../../components/RunEventTimeline/RunEventTimeline'
import { useRunEvents } from '../../hooks/useRunEvents'
import type { ChatMessage, Citation } from '../../types'
import styles from './WorkbenchView.module.css'

export function WorkbenchView() {
  const { events } = useRunEvents()
  const [messages] = useState<ChatMessage[]>([])
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null)

  // 占位：当前无真实答案，引用列表为空。后端就绪后由 answer 派生。
  const citations: Citation[] = []

  return (
    <div className={styles.workbench}>
      <section className={styles.mainCol}>
        <div className={styles.chatThread}>
          <ChatThread messages={messages} onCitationClick={setActiveChunkId} />
        </div>
        <div className={styles.citation}>
          <CitationPanel citations={citations} activeChunkId={activeChunkId} />
        </div>
        <div className={styles.composer}>
          <ChatComposer onSend={() => { /* 占位：后端就绪后发起问答 */ }} />
        </div>
      </section>
      <aside className={styles.sideCol}>
        <div className={styles.stageSlot}>像素 Agent 舞台（Task 8 填入）</div>
        <div className={styles.timelineSlot}>
          <RunEventTimeline events={events} />
        </div>
      </aside>
    </div>
  )
}
```

- [ ] **Step 6: 验证**

```bash
cd frontend
npm run typecheck
npm run dev
```

Expected: 工作台五区显示对应占位（空状态文案）；输入框可输入、点发送清空；无类型错误。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/ -A
git commit -m "feat(frontend): 工作台子组件占位（引用联动 + 事件时间线接通）"
```

---

### Task 8: 像素管理员组件（idle 动作样板 + 状态映射 + 开发预览）

**Files:**
- Create: `frontend/src/components/PixelAgent/PixelAgent.tsx`
- Create: `frontend/src/components/PixelAgent/PixelAgent.module.css`
- Create: `frontend/src/components/PixelAgent/animations.css`
- Create: `frontend/src/components/PixelAgent/stageMap.ts`
- Modify: `frontend/src/views/WorkbenchView/WorkbenchView.tsx`（舞台槽位填入 PixelAgent）

**Interfaces:**
- Consumes: `Stage`（Task 3）。
- Produces:
  - `stageMap: Record<Stage, { label: string; animclass: string; scene: string }>` —— stage → 动作配置映射。
  - `PixelAgent` props `{ stage: Stage; devControls?: boolean }` —— 渲染分层小人；`devControls` 为 true 时显示开发用 stage 切换器（非生产）。

- [ ] **Step 1: 创建 stageMap 映射表**

创建 `frontend/src/components/PixelAgent/stageMap.ts`：

```ts
import type { Stage } from '../../types'

// stage → 动作配置。animClass 对应 animations.css 里的类名；
// scene 是工作间场景元素描述（占位阶段用文字标识，便于后续替换为像素道具）。
export const stageMap: Record<
  Stage,
  { label: string; animClass: string; scene: string }
> = {
  idle: { label: '待命', animClass: 'anim-idle', scene: '安静的工作间' },
  uploading: { label: '搬运文档', animClass: 'anim-uploading', scene: '门口收件筐' },
  parsing: { label: '拆文件', animClass: 'anim-parsing', scene: '拆包台' },
  extracting: { label: '贴实体标签', animClass: 'anim-extracting', scene: '标签贴纸' },
  linking: { label: '拉关系线', animClass: 'anim-linking', scene: '连线板' },
  indexing: { label: '整理档案柜', animClass: 'anim-indexing', scene: '档案柜抽屉' },
  searching: { label: '翻找文件', animClass: 'anim-searching', scene: '文件堆' },
  checking: { label: '校对引用', animClass: 'anim-checking', scene: '放大镜' },
  writing: { label: '打字输出', animClass: 'anim-writing', scene: '打字机' },
  deleting: { label: '碎纸', animClass: 'anim-deleting', scene: '碎纸机' },
  rebuilding: { label: '复印重排', animClass: 'anim-rebuilding', scene: '复印机' },
  error: { label: '查看错误', animClass: 'anim-error', scene: '红色纸条' },
}

// 12 个状态的固定顺序，供开发预览切换器使用。
export const ALL_STAGES: Stage[] = [
  'idle', 'uploading', 'parsing', 'extracting', 'linking', 'indexing',
  'searching', 'checking', 'writing', 'deleting', 'rebuilding', 'error',
]
```

- [ ] **Step 2: 创建分层小人结构**

创建 `frontend/src/components/PixelAgent/PixelAgent.tsx`：

```tsx
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
```

- [ ] **Step 3: 创建小人结构样式**

创建 `frontend/src/components/PixelAgent/PixelAgent.module.css`：

```css
.stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  height: 100%;
  justify-content: center;
  image-rendering: pixelated;
}

.scene {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.agent {
  position: relative;
  width: 48px;
  height: 64px;
}

.head {
  position: absolute;
  top: 0;
  left: 12px;
  width: 24px;
  height: 20px;
  background: #fcd9b6;
  border-radius: 2px;
}

.glasses {
  position: absolute;
  top: 7px;
  left: 2px;
  width: 20px;
  height: 4px;
  background: var(--color-accent);
  opacity: 0.7;
}

.body {
  position: absolute;
  top: 20px;
  left: 8px;
  width: 32px;
  height: 28px;
  background: var(--color-accent);
  border-radius: 2px;
}

.armLeft, .armRight {
  position: absolute;
  top: 22px;
  width: 6px;
  height: 18px;
  background: #fcd9b6;
}

.armLeft { left: 4px; transform-origin: top center; }
.armRight { right: 4px; transform-origin: top center; }

.prop {
  position: absolute;
  top: 48px;
  left: 18px;
  width: 12px;
  height: 12px;
  background: var(--color-accent-border);
  opacity: 0;
}

.label {
  font-size: var(--text-sm);
  color: var(--color-accent);
  font-weight: 600;
}

.devControls {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  justify-content: center;
  margin-top: var(--space-2);
}

.devBtn, .devBtnActive {
  font-size: 10px;
  padding: 2px 4px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 2px;
}

.devBtnActive {
  background: var(--color-accent-soft);
  border-color: var(--color-accent-border);
  color: var(--color-accent);
}
```

- [ ] **Step 4: 创建动画定义（idle 可见 + 其余占位）**

创建 `frontend/src/components/PixelAgent/animations.css`：

```css
/* idle：呼吸 + 偶尔眨眼。做出可见效果，作为 CSS 分层方案的样板。 */
@keyframes breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

.anim-idle {
  animation: breathe 2.4s ease-in-out infinite;
}

/* 以下 11 个状态为占位：先复用一个轻微动作，保证类名存在、可被 stageMap 引用。
   后续按 frontend/docs/pixel-agent-guide.md 的步骤逐个补全为对应拟物动作。 */
@keyframes nudge {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-1px); }
}

.anim-uploading,
.anim-parsing,
.anim-extracting,
.anim-linking,
.anim-indexing,
.anim-searching,
.anim-checking,
.anim-writing,
.anim-deleting,
.anim-rebuilding {
  animation: nudge 1.2s ease-in-out infinite;
}

/* error：定格 + 轻微抖动，区别于进行中状态。 */
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-1px); }
  75% { transform: translateX(1px); }
}

.anim-error {
  animation: shake 0.5s ease-in-out 2;
}
```

- [ ] **Step 5: 在工作台舞台填入 PixelAgent**

修改 `frontend/src/views/WorkbenchView/WorkbenchView.tsx`：

顶部新增导入：

```tsx
import { PixelAgent } from '../../components/PixelAgent/PixelAgent'
```

从 `useRunEvents()` 解构出 `currentStage`：

```tsx
  const { events, currentStage } = useRunEvents()
```

将舞台槽位替换为：

```tsx
        <div className={styles.stageSlot}>
          <PixelAgent stage={currentStage} devControls={import.meta.env.DEV} />
        </div>
```

- [ ] **Step 6: 验证 idle 动作与开发预览**

```bash
cd frontend
npm run typecheck
npm run dev
```

Expected: 工作台右上舞台出现分层小人，持续做呼吸上下浮动（idle 样板生效）；下方出现 12 个 stage 切换按钮（开发模式），点击不同 stage 标签文字与场景文字随之变化。

```bash
npm run build
```

Expected: 生产构建成功（`import.meta.env.DEV` 在生产为 false，开发预览按钮不渲染）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/ -A
git commit -m "feat(frontend): 像素管理员组件（idle 动作样板 + stageMap + 开发预览）"
```

---

### Task 9: 指导文件与前端 DEVLOG

**Files:**
- Create: `frontend/docs/pixel-agent-guide.md`
- Create: `frontend/README.md`
- Create: `frontend/DEVLOG.md`

**Interfaces:**
- Consumes: 全部前述任务的产出（用于在文档中准确引用文件路径与类型名）。
- Produces: 三份面向人类读者的文档，无代码接口。

- [ ] **Step 1: 编写像素 Agent 动画指南**

创建 `frontend/docs/pixel-agent-guide.md`：

```markdown
# 像素 Agent 动画指南

像素管理员是 graphrag-kg-agent 的吉祥物：一个戴眼镜的档案管理员，根据后端
运行状态做出 12 种拟物动作。本文是维护和扩展它的指南。

## 红线（不可破）

**动画状态必须来自真实 RunEvent。** 数据流是单向的：

    后端 RunEvent → useRunEvents 钩子 → currentStage → PixelAgent

`PixelAgent` 的 `devControls` 仅供开发预览（手动切 stage 看效果），
**禁止用它驱动生产状态**。生产中 stage 只能从真实事件派生。

## 文件结构

- `src/components/PixelAgent/PixelAgent.tsx` —— 分层小人结构（头/身/左右手/道具）。
- `src/components/PixelAgent/PixelAgent.module.css` —— 各图层定位与尺寸。
- `src/components/PixelAgent/animations.css` —— 每个 stage 的 @keyframes。
- `src/components/PixelAgent/stageMap.ts` —— stage → {label, animClass, scene} 映射。

## 12 个状态动作表

| stage | 动作 | 场景元素 |
|---|---|---|
| idle | 待命，呼吸/眨眼 | 安静的工作间 |
| uploading | 搬运文档进门 | 门口收件筐 |
| parsing | 蹲下拆文件包 | 拆包台 |
| extracting | 贴实体标签 | 标签贴纸 |
| linking | 拉关系线 | 连线板 |
| indexing | 归档进档案柜 | 档案柜抽屉 |
| searching | 翻找文件 | 文件堆 |
| checking | 放大镜校对引用 | 放大镜 |
| writing | 打字输出 | 打字机 |
| deleting | 塞进碎纸机 | 碎纸机 |
| rebuilding | 复印重排 | 复印机 |
| error | 看错误纸条挠头 | 红色纸条 |

## 当前完成度

`idle` 已做出可见的呼吸动画作为 CSS 分层方案样板。其余 11 个状态的
animClass 已就位，但动作是占位（轻微浮动）。

## 加 / 完善一个状态的步骤

1. 在 `stageMap.ts` 确认该 stage 的 `label` 与 `scene` 文案。
2. 在 `animations.css` 为它的 `animClass`（如 `.anim-writing`）写专属
   `@keyframes`，驱动 `PixelAgent.module.css` 里的图层（手臂摆动用
   `.armLeft/.armRight` 的 transform，道具进出场用 `.prop` 的 opacity/transform）。
3. `npm run dev`，用开发预览切到该 stage 检查效果。
4. 状态切换的平滑（最短停留、排队）在 useRunEvents 接入真实 SSE 时实现：
   只平滑/排队已发生的真实事件，绝不伪造未发生的事件。

## 后续升级方向

当前为 CSS 分层 + keyframes 方案（方案 B）。有余力可升级为逐帧
sprite sheet（方案 A），届时替换 `animations.css` 与图层渲染方式，
但 stageMap 与 useRunEvents 的接口保持不变。
```

- [ ] **Step 2: 编写前端 README**

创建 `frontend/README.md`：

```markdown
# graphrag-kg-agent 前端

GraphRAG 工作台前端：React + Vite + TypeScript。

## 启动

    cd frontend
    cp .env.example .env   # 按需修改 VITE_API_BASE_URL
    npm install
    npm run dev

## 脚本

- `npm run dev` —— 开发服务器
- `npm run build` —— 生产构建
- `npm run preview` —— 预览生产构建
- `npm run typecheck` —— TypeScript 类型检查

## 当前状态

工程脚手架阶段：顶部导航 + 三视图（问答工作台 / 文档库 / 图谱）+ 设置页
均为占位实现；数据钩子与 API 客户端留接口、返回占位，未接业务后端。
像素管理员 idle 动作已可见，其余状态留占位。

## 结构

- `src/types/` —— 数据契约类型（前端需求版）
- `src/api/` —— fetch 封装（对接统一错误结构）
- `src/hooks/` —— useRunEvents（事件流钩子，预留 SSE）
- `src/views/` —— 三视图 + 设置
- `src/components/` —— TopBar / 工作台子组件 / PixelAgent
- `src/styles/` —— 设计 token 与全局样式
- `docs/pixel-agent-guide.md` —— 像素 Agent 动画维护指南

设计规格见 `../docs/superpowers/specs/2026-06-17-frontend-workbench-design.md`。
```

- [ ] **Step 3: 编写前端 DEVLOG 学习记录**

创建 `frontend/DEVLOG.md`：

```markdown
# 前端学习记录（DEVLOG）

## 2026-06-17 搭建前端工程脚手架（Vite + React + TS）

- 做了什么：用 Vite 初始化 React + TypeScript 工程，建立设计系统 token、
  数据类型、三视图与设置页占位、像素管理员组件（idle 动作可见），并写好
  启动说明与动画维护指南。

- 这是什么：
  - **Vite** 是前端构建/开发工具。它提供一个极快的本地开发服务器（改代码
    立刻热更新），并在发布时把代码打包成浏览器能高效加载的静态文件。相比
    老一代工具（如 webpack）启动和热更新快很多。
  - **React** 是构建用户界面的库。核心思想是"组件"——把界面拆成一个个可复用
    的函数（如 TopBar、PixelAgent），每个组件根据数据（props/state）渲染出
    一段界面，数据变了界面自动更新。
  - **TypeScript** 是给 JavaScript 加了"类型"的语言。比如规定一个函数必须收到
    `Stage` 类型的参数，写错了编译期就报错，而不是等运行时才崩——这对多人/
    多窗口协作尤其有价值。
  - **CSS Modules** 是一种写样式的方式：每个组件配一个 `.module.css`，里面的
    类名只对该组件生效，不会和别的组件撞名。配合 **CSS 变量**（定义在
    `tokens.css` 的 `--color-accent` 等）集中管理配色和间距。

- 为什么需要：前端是整个项目的"门面"，要把文档入库、问答、引用、图谱、运行
  状态都呈现给人看。先搭好骨架（导航、视图划分、数据类型、设计系统），后续
  填业务逻辑时就有稳定的地基，不必反复调整结构。

- 为什么这么做（选型理由）：
  - **不引 Tailwind，用 CSS Modules + CSS 变量**：项目规范"优先简单稳定"。
    浅色设计系统用一组 CSS 变量就能统一管理，不必引入额外的工具链。
  - **数据类型先行（src/types/）**：后端业务接口还没实现，但前端需要哪些
    数据是清楚的。先把 RunEvent / Answer / Citation 等类型写出来，既是"前端
    数据需求清单"，也让占位组件能带着正确的 props 类型搭起来，后端契约定了
    再填实现，不返工。
  - **像素小人与事件流共享一个数据源（useRunEvents）**：这是硬规则"动画必须
    来自真实 RunEvent"的技术保证——两者读同一份事件，永不脱节。当前钩子返回
    占位空流，预留了接 SSE 的位置。
  - **idle 动作先做出来**：用一个会"呼吸"的分层小人验证 CSS 分层动画方案
    可行，作为后续 11 个状态的样板，避免一次性铺开 12 个动作却跑偏。

- 踩了什么坑：
  - Vite 模板自带 `index.css` / `App.css`，我们的设计系统从 `tokens.css` +
    `global.css` 起，所以删掉模板样式、改了 `main.tsx` 的引入，避免两套样式
    打架。
  - 开发预览开关用 `import.meta.env.DEV` 控制：这是 Vite 注入的环境标志，
    开发时为 true、生产构建为 false——保证手动切 stage 的调试按钮绝不会出现在
    生产里，守住"不伪造状态"的红线。
```

- [ ] **Step 4: 验证文档完整**

```bash
cd frontend
ls docs/pixel-agent-guide.md README.md DEVLOG.md
```

Expected: 三个文件均存在。

- [ ] **Step 5: 提交**

```bash
git add frontend/docs/ frontend/README.md frontend/DEVLOG.md -A
git commit -m "docs(frontend): 像素 Agent 动画指南、README 与 DEVLOG 学习记录"
```

---

## 自检（Self-Review）记录

**Spec 覆盖**：
- §1 目标与边界 → 体现在 Global Constraints 与各任务占位约定 ✓
- §2 信息架构与导航 → Task 5（TopBar 三 tab + 设置）✓；迷你 Run 状态指示为规格提及的增强项，脚手架阶段未单独建任务（依赖真实 Run，留待后端就绪），已在此标注为已知缺口。
- §3 工作台组件分解与数据需求 → Task 6（布局）+ Task 7（子组件 + 引用联动 + 数据需求 props）✓
- §4 像素 Agent 状态机 → Task 8（stageMap 12 状态 + idle 样板 + 开发预览 + 单向数据流）✓
- §5 工程脚手架与设计系统 → Task 1（工程）+ Task 2（token）+ Task 3（类型）+ Task 9（指导文件）✓
- §6 硬规则对照 → Global Constraints 逐条承接 ✓

**已知缺口（有意不做）**：全局栏"迷你 Run 状态指示"依赖真实 Run 数据，脚手架阶段不实现，后端就绪后补；此为规格 §2 的增强项，不影响脚手架交付完整性。

**占位符扫描**：无 TBD/TODO 残留；文中"占位"均为脚手架的有意占位实现（每处都给了完整可运行代码）。✓

**类型一致性**：`Stage`（12 值）跨 Task 3/4/8 一致；`ChatMessage`/`Citation` 在 Task 3 定义、Task 7 消费一致；`ViewKey` 在 Task 5 定义、Task 6 使用一致；`useRunEvents` 返回 `{ events, currentStage }` 在 Task 4 定义、Task 7/8 消费一致。✓
