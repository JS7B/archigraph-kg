# 前端工作清单（喂给 feat/frontend 窗口）

> 大脑（main 窗口）整理。前端窗口请按此推进 P1→P3；P0 像素小人由用户亲自在本窗口调，不在此清单的代理范围内（但下方列出其约束供参考）。

## 开工前（必做）

```bash
cd E:\Mine\graphrag-kg-agent-frontend
git merge main          # feat/frontend 落后 main（后端已合 Neo4j 板块），先同步
```
同步后确认 `npm run typecheck` 与 `npm run build` 仍通过，再开始。

## 总原则

- **UI 的“形”不依赖后端，只有“真实数据”依赖后端**。本轮全部用 mock 数据把界面做完整、做精致，后端 API 就绪后只需把 mock 换成真实 `apiFetch` 调用。
- **mock 数据类型严格对齐 `src/types/`**（下方契约），将来换真实数据零摩擦。
- 设计基调遵循已定取向：浅色专业、往高级精致方向做；动画/状态相关遵守硬规则「动画状态来自真实 RunEvent，前端不编造」。
- 遵守 DEVLOG 约定：完成后在 `frontend/DEVLOG.md` 追加学习记录。

## 优先级与工作单元

### P1 设计系统打磨 + 共享 UI 基件
- 收敛 `src/styles/tokens.css`：色板（浅色专业）、间距尺度、字体层级、圆角/阴影，往“高级精致”定调。
- 抽出基础组件（按钮、卡片、面板容器、标签 chip、状态徽标等），供三视图复用。
- **先做这个**：后面三视图直接复用，避免做完视图再返工调样式。
- 验证：建一个临时预览页或 Storybook 式展示，肉眼确认基件风格统一。

### P2 三视图静态界面（mock 数据）
- **WorkbenchView**：问答 + 引用 + 事件时间线 + 像素小人 四区布局（布局 A，已有骨架），用 mock `ChatMessage[]` / `RunEvent[]` 填充。
- **LibraryView**：文档库，用 mock `DocumentMeta[]` 渲染文档卡片列表（含解析/索引状态徽标、chunk 数）。
- **GraphView**：Cytoscape 容器，用 mock `GraphData` 渲染一张小图（节点+边），验证布局/交互（缩放、点选）。
- 验证：三视图都能用 mock 数据渲染出完整界面，`npm run build` 通过。

### P3 CitationPanel 引用面板（mock）
- 用 mock 引用数据展示来源 chunk：文档名、位置、原文片段，支持点击角标定位。
- 验证：点击答案中的引用角标，面板高亮/滚动到对应来源。

## mock 数据契约（对齐 `src/types/`，勿自造冲突字段）

直接复用以下已定义类型（`src/types/index.ts` 统一导出），mock 照其结构造：

- `RunEvent { stage, status, message, timestamp }`，`Stage` = 12 状态（idle/uploading/parsing/extracting/linking/indexing/searching/checking/writing/deleting/rebuilding/error）。
- `DocumentMeta { id, name, sourceType, parseStatus, indexStatus, chunkCount }`。
- `GraphData { nodes: GraphNode[], edges: GraphEdge[] }`。
- `ChatMessage { id, role, text, answer? }` / `Answer { id, text, confidence, citations }` / `Citation { index, chunkId, documentName, location, snippet }`。

### ⚠️ 一个待对齐点（现在不阻塞，接真实 API 时再处理）
前端 `Citation` 用 `documentName / location / snippet`，而后端检索结果 `ChunkHit` 是
`chunk_id / document_id / chunk_index / text / char_start / char_end / page / heading_path / score`。
两者字段不一致。**本轮 mock 仍按前端 `Citation` 造**即可；等接真实 `/api/chat` 或检索 API 时，由大脑统一定一层映射（后端 ChunkHit → 前端 Citation），不要现在擅自改类型。

## P0 像素小人（用户亲自调，列此仅供前端窗口知边界）
- 不在代理范围。用户在本窗口手动做 12 状态动画。
- 硬约束：动画状态只能由 `RunEvent.stage` 驱动（`useRunEvents` 已守住红线），前端窗口若动到 PixelAgent 相关文件需先与用户确认，避免与用户的手动调整冲突。

## 交接
完成一个 P 单元就本地 commit（信息写清做了什么），由用户口头通知大脑窗口分支名，大脑读 diff 评审、合并。绝不自行合并 main。
