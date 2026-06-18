# 前端 → 后端 接口需求清单

日期：2026-06-17
来源：前端工作台脚手架（`feat/frontend`）的真实数据需求，字段对齐 `frontend/src/types/`。
性质：**协商起点 + 推荐形态**，非冻结契约（遵循项目"先跑通再命名"原则）。后端可调整命名/结构，但请保留字段语义；改动后同步前端 `types/`。

> 统一约定：
> - 所有响应 JSON 字段用 **camelCase**（前端 TS 类型即如此）。后端若内部用 snake_case，请在序列化层转换。
> - 错误统一走已实现的 `{"error": {"type", "message"}}` 结构（前端 `apiFetch` 已对接）。
> - base URL 由前端 `VITE_API_BASE_URL` 配置，默认 `http://localhost:8000`。

---

## 优先级总览（建议后端按此顺序推进）

| 优先级 | 能力 | 解锁的前端 | 依赖 |
|---|---|---|---|
| **P0（已就绪）** | `/health`、`/health/deps` | 设置页依赖状态、顶部栏 Neo4j/LLM 状态灯 | 已实现 ✅ |
| **P1** | 文档库 CRUD：列表/上传/删除 | 文档库视图（有东西可问） | 文档解析+入库 |
| **P2** | 问答 + Run 事件流（SSE） | 问答工作台 + **像素 Agent 动画**（项目灵魂） | GraphRAG 检索、Run/RunEvent |
| **P3** | 图谱查询 | 图谱探索视图 | 实体/关系已入库 |

P1+P2 合起来就能跑通核心演示闭环：**上传文档 → 像素小人动画展示处理过程 → 提问 → 得到带引用的答案**。P3 是可视化增强。

---

## P0 · 健康检查（已实现，前端可直接接）

```
GET /health        → { "status": "ok" }
GET /health/deps   → { "neo4j": "ok" | "error: ...", "llm": "configured" | "not_configured" }
```

前端用途：设置页展示依赖连通状态；顶部栏 Neo4j/LLM 状态灯。**这是当前唯一前端能立即对接的真实接口。**

---

## P1 · 文档库（对应前端 `DocumentMeta`）

前端类型（`types/document.ts`）：
```ts
sourceType: 'pdf' | 'markdown' | 'txt' | 'repo'
parseStatus: 'pending' | 'parsing' | 'parsed' | 'failed'
indexStatus: 'pending' | 'indexing' | 'indexed' | 'failed'
DocumentMeta { id, name, sourceType, parseStatus, indexStatus, chunkCount }
```

### 接口

```
GET /api/documents
→ DocumentMeta[]

POST /api/documents          （multipart 文件上传，或 { repoPath } 导入本地仓库目录）
→ { runId: string, document: DocumentMeta }
  说明：入库是异步过程（解析→切块→embedding→抽取→写图谱），立即返回 runId，
        前端用它订阅事件流看进度（见 P2 的 SSE）；document 初始 parseStatus/indexStatus 为 pending/parsing。

GET /api/documents/{id}
→ DocumentMeta          （前端轮询或事件结束后刷新，拿最终状态与 chunkCount）

DELETE /api/documents/{id}
→ { runId: string }     （删除也是一次 Run：清理 chunk/mention/embedding/孤立实体；前端可看碎纸机动画）
```

> 待后端确认：上传是「先存原文件、后台起 Run 处理」还是「同步处理完再返回」。前端倾向**异步 + runId**，这样像素动画才有进度可演。

---

## P2 · 问答 + Run 事件流（项目核心）

### 2.1 RunEvent 流（驱动像素 Agent + 事件时间线）

前端类型（`types/runEvent.ts`），**字段务必对齐**：
```ts
Stage = 'idle'|'uploading'|'parsing'|'extracting'|'linking'|'indexing'
      |'searching'|'checking'|'writing'|'deleting'|'rebuilding'|'error'
RunEventStatus = 'started' | 'progress' | 'done' | 'failed'
RunEvent { stage: Stage, status: RunEventStatus, message: string, timestamp: number /*ms*/ }
```

```
GET /api/runs/{runId}/events/stream      （SSE，text/event-stream）
每条事件：data: {"stage":"extracting","status":"progress","message":"已抽取 12 个实体","timestamp":1718600000000}\n\n
  - 前端 useRunEvents 订阅它，把事件累积进 events，currentStage = 最新事件的 stage。
  - 红线：像素小人动作只认这些真实事件，前端绝不编造。
  - 结束：发完终态事件（status:"done" 或 "failed"）后关闭流；或发一个约定的 [DONE] 哨兵。
  - stage 取值必须落在上面 12 个枚举内（这是像素小人的动作映射键）。

GET /api/runs/{runId}/events             （非流式兜底：一次性返回 RunEvent[]，供刷新/补抓历史）
→ RunEvent[]

GET /api/runs/{runId}                    （可选：Run 概况）
→ { id, kind: 'chat'|'ingest'|'delete'|'reindex', status, ... }
```

> Stage ↔ 后端阶段映射建议：
> 入库 Run 走 `uploading→parsing→extracting→linking→indexing→done`；
> 问答 Run 走 `searching→checking→writing→done`；
> 删除走 `deleting`，重建走 `rebuilding`，任何失败发 `error`。
> 后端只要在各处理阶段 emit 对应 stage 的 RunEvent 即可，前端自动把它变成小人动作。

### 2.2 问答（对应前端 `Answer` / `Citation` / `ChatMessage`）

前端类型（`types/answer.ts`），**字段务必对齐**：
```ts
Citation { index: number /*角标号,从1起*/, chunkId: string, documentName: string, location: string, snippet: string }
Answer { id, text, confidence: 'high'|'medium'|'low', citations: Citation[] }
```

```
POST /api/chat            body: { question: string }
推荐形态（异步，配合像素动画）：
→ { runId: string }
  前端拿 runId 立即打开 SSE 看 searching→checking→writing 动画；
  生成完成后，最终答案通过以下任一方式给到前端（二选一，待后端定）：
    (a) SSE 的终态事件里带 answer 字段：data: {"stage":"writing","status":"done","answer":{...Answer}}
    (b) 前端在收到 done 后 GET /api/runs/{runId} 取 { answer: Answer }
  前端倾向 (a)，少一次往返。

  简单兜底形态（同步，先跑通用）：
→ Answer                  （直接返回完整 Answer，暂不接 SSE 动画；P2 初版可先这样）
```

**引用可追溯硬要求**：`Citation.chunkId` 必须能在前端反查原文。需要一个取 chunk 原文的接口（点引用角标时展开）：
```
GET /api/chunks/{chunkId}
→ { chunkId, documentName, location, text }     （前端 CitationPanel 展开原文用；
   若 POST /api/chat 的 Citation.snippet 已含足够原文，可不单独实现此接口——待定）
```

---

## P3 · 图谱查询（对应前端 `GraphData`，Cytoscape.js 渲染）

前端类型（`types/graph.ts`）：
```ts
GraphNode { id, label, entityType }
GraphEdge { id, source, target, relationType }   // 业务关系先统一 :RELATES，类型作属性
GraphData { nodes: GraphNode[], edges: GraphEdge[] }
```

```
GET /api/graph/entities?limit=...            → GraphData         （图谱概览/初始视图）
GET /api/graph/entities/{id}/neighbors       → GraphData         （点节点展开邻域）
GET /api/graph/search?q=...                  → GraphNode[]        （实体搜索）
```

> 关系类型：按项目决策先统一 Neo4j `:RELATES`，把业务类型放进 `relationType` 属性，前端照常读 `relationType` 渲染标签。

---

## 给后端的最小起步建议

如果想最快让前端"活"起来、看到像素小人动起来，最小切片是：

1. **P1 的 `GET /api/documents` + `POST /api/documents`（返回 runId）**
2. **P2.1 的 SSE `/api/runs/{runId}/events/stream`**（哪怕先在入库流程里 emit 几个 stage 事件）

这两步一通，前端就能演示「上传 → 像素小人按真实阶段动画」的核心记忆点。问答（P2.2）和图谱（P3）随后补。

每实现一个接口，告诉前端实际的最终字段/形态，前端把对应的占位钩子（`useRunEvents`、各视图的占位数据）换成真调用即可——脚手架已经为每个都留好了接入位置。
