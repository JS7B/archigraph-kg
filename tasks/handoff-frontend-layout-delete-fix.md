# 前端交接清单 · 工作台布局重排 + 文档删除确认（feat/frontend）

> 大脑整理，交 feat/frontend 窗口执行。**开工前先 `git merge main` 同步最新 main**（main 现领先一个后端提交 e72c084，纯后端改动，合过来无冲突）。
> 两个独立的前端体验修正，均不涉及后端。

## 一、要做什么（两件事）

1. **工作台布局重排**：引用证据面板从中列挪到右列；AgentRoom 下方状态文字替换为 Run Events 轨迹。解决"对话区被引用面板挤得太小"。
2. **文档删除确认**：文档库删除改为弹窗确认（二次确认），确认后才带 `confirm=true` 调后端。解决"点删除只报错不删"。

---

## 二、任务 1：工作台布局重排

### 2.1 问题

`WorkbenchView` 中列（`.mainCol`）塞了三块：`ChatThread`(flex:1) + `CitationPanel`(max-height:240px) + `ChatComposer`。引用面板占 240px 固定高，挤占对话区，开始对话后对话窗口很小不好看。

### 2.2 目标布局

**现状**：
```
[ConversationSidebar] | [ChatThread + CitationPanel + ChatComposer] | [AgentRoom + RunEventTimeline]
```

**目标**：
```
[ConversationSidebar] | [ChatThread + ChatComposer] | [AgentRoom + CitationPanel]
                                                   ↑ 对话区变大（引用面板移走）
                      且 AgentRoom 组件内部：
                      下方原 .status（label/detail 状态文字）→ 去掉
                      换成显示 RunEventTimeline（运行轨迹）
```

### 2.3 改动要点

**WorkbenchView.tsx**：
- 中列（`.mainCol`）移除 `CitationPanel`，只剩 `ChatThread` + `ChatComposer`。
- 右列（`.sideCol`）：`AgentRoom` + `CitationPanel`（替代原来的 `RunEventTimeline` 面板）。
- 右列的 `RunEventTimeline` **从右列移除**（它的内容并进 AgentRoom 下方，见下）。
- `citations` 派生逻辑（WorkbenchView.tsx 当前从"最近一条 agent 消息"取 citations）**不变**，只是渲染位置从中间挪到右列。`activeChunkId` / `onCitationClick` 联动逻辑不变。

**AgentRoom.tsx**：
- 下方 `.status` 区（当前渲染 `cfg.label` + `cfg.detail`，约 AgentRoom.tsx:92-94）**整个去掉**。
- 在原 `.status` 位置渲染 `RunEventTimeline`（接收 `events` props）。
- 即：AgentRoom 组件新增 `events` props（`RunEvent[]`），内部下方放 `<RunEventTimeline events={events} />`。
- `sceneMap.ts` 的 label/detail/busy 配置**不删**（`busy` 仍用于驱动 `data-busy` 动画，label/detail 只是不再显示文字）。
- **红线守**：`stage` 仍只来自真实 RunEvent，不伪造。AgentRoom 的 `stage` prop 不变。

**WorkbenchView.module.css**：
- `.mainCol`：移除 `.citation` 相关。
- `.citation` 样式挪到右列（`.sideCol` 下），可能要调 flex 比例（AgentRoom 和 CitationPanel 在右列怎么分高度）。
- `.sideCol`：现在是 AgentRoom(flex:1.2) + Timeline(flex:1)；改成 AgentRoom(flex:1.2) + CitationPanel(flex:1) 或类似。
- 删除原 `.timelinePanel` 相关（或复用 class 名给 CitationPanel，看你怎么顺）。
- 响应式断点（@media max-width:860px）同步调整：堆叠时 CitationPanel 也要有合理高度。

**RunEventTimeline**：组件本身不改，只是从 WorkbenchView 的右列移到 AgentRoom 内部渲染。注意 props 传递：WorkbenchView 把 `events` 传给 AgentRoom，AgentRoom 再传给内部的 RunEventTimeline。

### 2.4 注意

- AgentRoom 拿到 `events` 后，内部布局要保证：像素小人画布（`.canvas`）仍是主体，RunEventTimeline 在下方不喧宾夺主（轨迹列表可限定 max-height + 滚动）。
- CitationPanel 挪到右列后，宽度变窄（右列原本就窄），注意引用条目的排版（snippet 可能要截断或换行）。
- 不要改 ConversationSidebar（左列不动）。

---

## 三、任务 2：文档删除弹窗确认

### 3.1 问题

`LibraryView.tsx::handleDelete`（约 :121-133）调 `DELETE /api/documents/{id}` **没传 `?confirm=true`**，后端按安全设计返回 400「删除是危险操作，需传 confirm=true 显式确认」。用户点删除只看到报错，没有删除流程。

### 3.2 目标

点删除 → 弹确认对话框（modal，和 ConversationSidebar 删除会话的确认框风格一致）→ 用户点「确认」→ 才带 `confirm=true` 调 DELETE。

### 3.3 改动要点

**LibraryView.tsx**：
- `handleDelete` 调用补 `?confirm=true`：
  ```ts
  `/api/documents/${encodeURIComponent(documentId)}?confirm=true`
  ```
- 删除按钮点击 → **先弹确认框**（不直接调 API）。参考 `ConversationSidebar.tsx` 的 `pendingDelete` + modal 模式：
  - 加 `pendingDelete` state（待确认的 documentId）
  - 点删除 → `setPendingDelete(documentId)`
  - 弹出 modal：「确定删除这个文档？删除后无法恢复。」+ 取消/确认按钮
  - 确认 → 调 `handleDelete(pendingDelete)` + 关闭弹窗
  - 取消 → 关闭弹窗
- modal 的无障碍：`role="dialog" aria-modal="true" aria-label="确认删除文档"`，确认按钮 `autoFocus`，键盘可达（和 ConversationSidebar 一致）。
- 可抽一个共享的 ConfirmDialog 组件，或直接在 LibraryView 内联（看复杂度，简单内联也行）。

**后端不改**：`?confirm=true` 的安全设计是对的，前端补上即可。

### 3.4 注意

- 删除是异步 Run（返回 runId），确认后走原有的 SSE 订阅 + 终态刷新列表逻辑，不变。
- `?confirm=true` 是 query param，apiFetch 的 DELETE 调用要把它拼进 URL（不是 body）。

---

## 四、边界与验证

- **不改后端、不改契约**。
- **红线守**：AgentRoom 的 stage 仍只来自真实 RunEvent。
- **无障碍不退化**：新弹窗、移动后的面板都要键盘可达、aria 完整。
- **typecheck + build**：改完务必跑 `npm run build`（`tsc -b` 比 `tsc --noEmit` 严）。
- **DEVLOG**（`frontend/DEVLOG.md`）：追加布局调整思路 + 删除确认交互。
- 联调：前后端都在跑（后端 8000、前端 5173、Neo4j 在跑），改完真机验证：
  - 对话区是否变大、引用面板在右列是否正常、AgentRoom 下方是否显示轨迹而非状态文字。
  - 文档删除：点删除弹确认框、确认后真删（列表刷新）。

## 五、验收

- [ ] 对话区（ChatThread）明显变大，不再被引用面板挤占。
- [ ] 引用证据面板在右列（AgentRoom 下方或旁边）正常显示。
- [ ] AgentRoom 下方显示 Run Events 轨迹（不再是「待命/抽取」状态文字）。
- [ ] 像素小人动画正常（stage 驱动不变）。
- [ ] 文档删除：点删除弹确认框，确认后才删（带 confirm=true），取消则不删。
- [ ] typecheck 零错误、build 通过。

## 六、交接

本地 commit（写清做了什么），**口头通知大脑分支名**，大脑读 diff 评审、合并。**不自行合并 main，不 push。**
