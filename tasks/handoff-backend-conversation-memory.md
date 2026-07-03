# 后端交接清单 · 多轮对话记忆（feat/backend）

> 大脑整理，交 feat/backend 窗口执行。**开工前先 `git merge main` 同步最新 main。**
> 设计方案由大脑与用户逐条确认定板（见末尾「设计决策」），技术路线勿再选型。
> 与前端并行：前后端通过下方「冻结契约」解耦，**后端先按契约实现**，前端按同一契约对接。

## 一、要做什么（一句话）

给问答补上**多轮对话记忆**：同会话内连续追问，Agent 能利用本会话近期历史上下文作答；历史以 `Conversation`/`Message` 节点存入 Neo4j 图谱，问答文本都向量化可被检索；提供会话 CRUD 接口。

## 二、冻结契约（前后端共用，后端严格按此输出，前端按此对接）

### 2.1 POST /api/chat（改：请求/响应加 conversationId）

**请求体**：

```json
{ "question": "它用什么图谱数据库？", "conversationId": null }
```

- `question`: str（必填）
- `conversationId`: str | null（**可空**）。`null`/缺省 = 首问，后端**自动建新会话**；非空 = 已有会话追问。

**响应体**：

```json
{ "runId": "abcd1234ef56", "conversationId": "conv_xxxxxxxxxxxx" }
```

- `runId`: str（不变，12 位）
- `conversationId`: str（**始终返回**，新建或既有）。前端拿这个存住、后续追问回传。

**SSE 终态事件**：`answer` 字段结构**不变**（仍 `{text, confidence, citations}`）。无需在 RunEvent 里带 conversationId（响应体已给）。

### 2.2 会话 CRUD（全新接口，REST）

```
GET    /api/conversations                        → 会话列表
POST   /api/conversations                        → 新建空会话
GET    /api/conversations/{conversationId}       → 单会话 + 全部消息
DELETE /api/conversations/{conversationId}       → 删会话
```

**GET /api/conversations 响应**（按 createdAt 降序）：

```json
{
  "items": [
    { "conversationId": "conv_aaaa", "title": "项目用什么图谱…", "createdAt": 1719000000000, "messageCount": 6 }
  ]
}
```

**POST /api/conversations**（请求体可选 `{title?}`，空则 title="新会话"）→ 响应同 2.3 单会话结构（messageCount=0, messages=[])。

**GET /api/conversations/{id} 响应**：

```json
{
  "conversationId": "conv_aaaa",
  "title": "项目用什么图谱…",
  "createdAt": 1719000000000,
  "messageCount": 6,
  "messages": [
    { "messageId": "conv_aaaa#1", "turnIndex": 1, "role": "user",  "text": "...", "confidence": null, "citations": [] },
    { "messageId": "conv_aaaa#2", "turnIndex": 2, "role": "agent", "text": "...", "confidence": "high", "citations": [{...Citation...}] }
  ]
}
```

- `role`: `"user"` | `"agent"`
- `confidence`: `"high"|"medium"|"low"`（user 为 `null`）
- `citations`: Citation 列表（结构同 chat 的 answer.citations：`{index, chunkId, documentId, location, snippet}`）；user 消息为 `[]`
- `createdAt`: 毫秒时间戳（与 Run 一致）

**DELETE /api/conversations/{id}**：异步删（参考现有 DELETE /api/documents 的 Run 模式，或同步删均可——**同步删更简单，本任务用同步**，返回 `204` 或 `{deleted: true}`）。

> 命名：所有对外字段 **camelCase**（沿用现有 `_CamelModel` + `by_alias=True` 模式）；内部 snake_case。

## 三、图谱 Schema 扩展

新增节点 + 约束 + 向量索引（追加到 `app/graph/schema.py`）：

```cypher
(:Conversation {conversation_id, title, created_at, message_count})

(:Message {
  message_id,           -- 确定性：f"{conversation_id}#{turn_index}"
  conversation_id, turn_index, role, text,
  citations,            -- agent 消息：JSON 字符串（序列化的 Citation 列表）；user 为 null
  confidence,           -- agent 消息 high/medium/low；user 为 null
  embedding,            -- 问答文本向量（user/agent 都做）
  created_at            -- 毫秒时间戳
})

(:Conversation)-[:HAS_MESSAGE]->(:Message)
```

- **约束**（追加到 `_CONSTRAINTS`，均 IF NOT EXISTS）：
  - `conversation_id_unique` → `(:Conversation) REQUIRE conversation_id IS UNIQUE`
  - `message_id_unique` → `(:Message) REQUIRE message_id IS UNIQUE`
- **向量索引**：新增 `MESSAGE_VECTOR_INDEX = "message_embedding"`，cosine，维度取 `get_settings().embedding_dim`，`FOR (m:Message) ON (m.embedding)`。在 `ensure_schema` 里并列建（复用 `db.awaitIndexes(120)`）。
- **幂等 id**：`message_id = f"{conversation_id}#{turn_index}"`（与 chunk_id 的 `#` 分隔一致）。turn_index 从 1 起。
- `main.py:_ensure_vector_index_dim`：**对消息索引也加维度兜底**（根治 L6 一致，防测试残留 8 维污染）。

## 四、实现要点（按依赖顺序）

### 1. 抽取 embed_texts（改 `app/graph/embedding.py`）

现状 `embed_chunks(doc)` 强耦合 `ParsedDocument`。抽一个通用的：

```python
def embed_texts(texts: list[str], *, batch_size: int = 64) -> list[list[float]]:
    """对任意文本列表批量 embed，与输入同序。首向量维度校验。"""
```

让 `embed_chunks` 内部改成 `embed_texts([c.text for c in doc.chunks])`（保留维度校验，不破坏现有行为）。消息向量化复用 `embed_texts`。

### 2. 新增 `app/conversations/` 模块

- `models.py`：`Conversation`（conversation_id/title/created_at/message_count）、`Message`（message_id/conversation_id/turn_index/role/text/citations/confidence/created_at）。**沿用 `app/qa/models.py:10-18` 的 `_CamelModel`（camelCase alias 基类）**。`Message.citations` 内部存 `list[Citation]`，写入图谱时 `json.dumps`，读出时 `json.loads`。
- `store.py`（图谱读写，函数均 `driver, *, database="neo4j"`）：
  - `create_conversation(driver, *, title="新会话") -> Conversation`
  - `add_message(driver, conversation_id, *, role, text, embedding, citations=None, confidence=None) -> Message`：**自动算 turn_index**（`MATCH (m:Message) WHERE m.conversation_id=$cid RETURN max(m.turn_index)` + 1，无则 1），幂等 MERGE by message_id，`SET` 全字段 + `embedding`，建 `HAS_MESSAGE` 边，更新 Conversation.message_count。
  - `get_messages(driver, conversation_id, *, limit=None) -> list[Message]`：按 turn_index 升序；limit 实现「注入窗口」（None=全量）。
  - `list_conversations(driver) -> list[Conversation]`：按 created_at 降序。
  - `get_conversation(driver, conversation_id) -> Conversation | None`
  - `delete_conversation(driver, conversation_id) -> bool`：DETACH DELETE Message + Conversation（参考 `_do_delete` 模式）。
  - conversation_id 生成：`f"conv_{uuid.uuid4().hex[:12]}"`。
- `__init__.py`：re-export。

### 3. Agent 接收历史（改 `app/qa/agent.py`）

- `answer_question_agentic` 加可选参数 `history: list[dict] | None = None`（默认 None，行为不变，**保证现有测试不回归**）。
- messages 构建：`[system, *history, {"role":"user","content":question}]`。history 是已规整的 `{role, content}` 列表（由 run_chat 把图谱 Message 转成）。
- **system prompt 微调**（`_AGENT_SYSTEM_PROMPT`）：补一句——「注意：上方可能有同会话的对话历史作为上下文参考，但**回答仍须基于本次检索到的【文档片段】并用 [n] 角标标注引用**，不得仅凭历史记忆作答」。守引用可追溯红线。
- `_generate_final_answer` 和工具逻辑**不动**（引用闭环不变）。

### 4. 降级路径同步（改 `app/qa/pipeline.py`）

- `answer_question` 也加 `history: list[dict] | None = None`，把 history 塞进 `build_answer_messages`。保证降级也有记忆。

### 5. 后台任务串联（改 `app/runs/tasks.py`）

`run_chat` 签名加 `conversation_id: str | None`。流程：

1. conversation_id 为 None → `create_conversation(title=question前30字)`，得到新 id。
2. 读近期历史：`get_messages(conv_id, limit=MAX_HISTORY_TURNS)`（模块级常量 `MAX_HISTORY_TURNS = 6`，即最近 3 组问答）。
3. 规整成 history（user→`{role:"user",content:m.text}`，agent→`{role:"assistant",content:m.text}`）。
4. 调 `answer_question_agentic(driver, question, history=history, on_event=_emit_cb)`。
5. 拿到 Answer 后，**写回本轮两条消息**（各 embed 一次）：
   - `add_message(conv_id, role="user", text=question, embedding=embed_texts([question])[0])`
   - `add_message(conv_id, role="agent", text=answer.text, embedding=embed_texts([answer.text])[0], citations=answer.citations, confidence=answer.confidence)`
6. 终态事件 `answer` 不变；conversation_id 通过响应体返回（见 chat 路由）。

- embed 调用是阻塞的，记得用 `asyncio.to_thread` 包裹（参考现有阻塞段写法）。
- 降级分支 `answer_question` 也要传 history、写回消息。

### 6. 路由层

- 改 `app/routers/chat.py`：`ChatRequest` 加 `conversation_id: str | None = None`；`ChatResponse` 加 `conversation_id: str`；`background_tasks.add_task(run_chat, driver, store, run.id, body.question, body.conversation_id)`。**conversation_id 由 run_chat 内部解析（None→新建）并通过返回/事件回传**——注意 run_chat 是异步任务，HTTP 响应里要先同步解析出 conversation_id：建议在 `chat()` 路由里，若 body.conversation_id 为 None，**同步** `create_conversation` 拿到 id 再传给 run_chat（避免异步任务未跑完前端拿不到 id）。已有会话直接透传。
- 新增 `app/routers/conversations.py`：实现 §2.2 四个端点，复用 `apiFetch` 风格的错误处理（参考现有 router）。
- `app/main.py`：`app.include_router(conversations_router)`。

## 五、硬规则与边界（必须守）

- **引用可追溯不退化**：历史注入后，答案仍带 `[n]` 角标且角标对应真实 chunk。绝不能让模型凭历史记忆瞎答（system prompt 已强约束）。
- **幂等**：重复写同 message_id（如任务重试）不翻倍——MERGE by message_id。
- **维度一致性**：消息向量索引维度 = chunk 向量索引维度 = `EMBEDDING_DIM`。embed_texts 维度校验保留。
- **memory 窗口**：注入只取最近 6 条（控 token），但全量存图谱。超窗口老历史不进 messages、不删。
- **测试不污染共享库**：conversations 测试用 `test_` 前缀的 conversation_id，teardown 清理（参考现有 graph/extraction 测试的清理约定）。**重要：消息向量索引测试用独立索引名（如 `message_embedding_test`）与生产物理隔离**（根治 L6，参考 chunk 索引的 test 隔离）。
- **Stage 枚举勿改名**：本次不加新 stage（记忆是后端内部行为，不产生新动画状态）。
- **API Key 中间件**：新路由自动受 `ApiKeyMiddleware` 保护（中间件全局），无需额外处理；DELETE 沿用现有 confirm 约定与否——**本任务会话删除较轻，可不要求 confirm，但需遵守中间件既有逻辑**。
- **装依赖**：本方案零新依赖（复用 neo4j driver / openai SDK / pydantic）。

## 六、测试与验证

- `backend/tests/conversations/test_store.py`：create/add/get/list/delete、turn_index 自增、幂等、citations 序列化往返、向量索引隔离。
- `backend/tests/conversations/test_api.py`：四个端点 happy path + 错误（404 不存在的会话）。
- `backend/tests/qa/test_agent.py`：加 `history` 参数用例（带历史时 messages 含历史、答案仍带引用）；现有用例不回归（history=None 默认）。
- `backend/tests/runs/test_tasks.py`：run_chat 带 conversation_id 的端到端（mock LLM + seed 图谱），验证历史读出 + 本轮写回 + 新会话创建。
- 真实 LLM 用例加 `is_configured` gate，未配置 skip。
- 跑 `pytest -q` 全量不退化（现有 126 passed）；新模块全过。
- 端到端手测：POST /api/chat 连续两问（第二问带第一问返回的 conversationId），看第二轮答案能正确指代。
- **DEVLOG**（`backend/DEVLOG.md`）：为什么对话进图谱（B 方案）、记忆窗口策略、向量索引隔离踩坑（若有）。

## 七、设计决策（大脑与用户已确认，背景知会）

| 维度       | 决策                                                                                                                    |
| ---------- | ----------------------------------------------------------------------------------------------------------------------- |
| 历史怎么用 | 近期注入上下文（滚动窗口 6 条），不做向量召回历史                                                                       |
| 存哪       | Neo4j 图谱（Conversation/Message 节点）                                                                                 |
| 会话 UI    | 多会话 + 侧边栏（前端做）                                                                                               |
| 记什么     | 问题+答案+引用证据                                                                                                      |
| 向量化     | 问答都向量化（建 message_embedding 索引），本次 Agent 工具**暂不**主动召回历史（schema 已铺路，留作后续体验增强） |

## 八、交接

本地 commit（写清做了什么），**口头通知大脑分支名**，大脑读 diff + 跑测试评审、合并。**不自行合并 main，不 push。**
