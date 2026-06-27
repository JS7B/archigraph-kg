# 后端交接清单 · 升级为 Agentic RAG（feat/backend）

> 大脑整理，交 feat/backend 窗口执行。开工前先 `git merge main` 同步（落后 main 多个提交）。
> 技术路线已调研定板，不要再选型。

## 一、要做什么（一句话）

把问答核心从「固定线性 pipeline」升级为 **Agentic RAG**：LLM 自主决策检索什么、判断证据够不够、不够就换查询再检索（ReAct 检索-反思循环），并在多个检索工具间自选。

## 二、技术路线（已定，勿改）

**纯自研轻量 while 循环 + OpenAI 原生 function calling（tool calling）**，不引 LangGraph/LangChain。
理由：单 agent + 内部工具场景，自写循环是主流共识，最大化保留编排控制权（符合「不被第三方框架牵着走」决策边界），零新依赖，复用现有检索组件。

## 三、现状（已核实）

- 现有线性版 `app/qa/pipeline.py::answer_question(driver, question)` —— 一次性 embed→召回→rerank→扩展→拼上下文→生成。**保留不删**（降级兜底 + 评估基线）。
- 可封装为工具的现成组件：
  - `app/graph/search.py::search_chunks(driver, query_embedding, top_k, database)` —— 注意要先 `llm.embed([query])` 拿向量再传（曾有 bug 直接传字符串）。
  - `app/qa/expand.py::expand_entities(driver, chunk_ids, database)` —— MENTIONS→RELATES 扩 1 跳。
  - `app/qa/rerank.py::rerank_chunks(query, hits, top_n)`。
  - `app/qa/context.py::build_context(chunks, paths) -> (context_str, citations)` —— [n] 角标↔Citation。
- `app/clients/llm.py::chat(messages, *, response_format)` —— **目前只支持文本返回，不支持 tools**，需扩展。
- RunEvent stage 枚举（`app/runs/models.py`）：idle/uploading/parsing/extracting/linking/indexing/searching/checking/writing/deleting/rebuilding/error（12 个，锁定前端契约，勿改名）。
- `app/runs/tasks.py::run_chat` —— 当前 emit 三个固定假阶段（searching/checking/writing）后调 answer_question。

## 四、实现要点

### 1. 新增 `app/qa/agent.py`：ReAct 循环
```
answer_question_agentic(driver, question, *, max_turns=4, on_event=None) -> Answer
  messages = [system(agent指令), user(question)]
  while turn < max_turns:
    msg = llm.chat_with_tools(messages, tools=TOOLS, tool_choice="auto")
    if msg.tool_calls:
      for tc in msg.tool_calls:          # 必须遍历执行每一个并都回传（并行调用坑）
        result = dispatch(tc, driver)    # 调对应检索组件
        messages.append(tool结果)         # 裁剪：只回 chunk_id+精简正文，控 token
        证据池.add(召回的 chunk)           # 去重累积，留 provenance
        if on_event: on_event(stage, msg) # 回调让 run_chat emit 真实事件
    else:
      return 解析答案 + 从证据池/build_context 出可追溯引用
  # 超 max_turns：用证据池强制生成兜底答案
```
- 工具集（每个一份 JSON Schema，`additionalProperties:false`，description 从模型视角写清何时用/返回什么）：
  - `vector_search(query: str)` → 包 search_chunks（内部先 embed，可顺带 rerank）
  - `expand_entity(chunk_ids: list[str])` → 包 expand_entities
  - 设计成易扩展（日后加「图谱路径查询」只加一个 tool，循环不动）。
- `on_event` 回调：让循环把每一步通知外部（run_chat 用它 emit RunEvent），agent.py 本身不依赖 RunStore（保持纯检索逻辑、可单测）。

### 2. 改造 `app/clients/llm.py`
- 新增 `chat_with_tools(messages, *, tools, tool_choice="auto")`，返回**完整 message 对象**（含 tool_calls + content）。
- `chat()` 保持不动（抽取板块在用）。
- tool 参数 `json.loads` 包 try/except 防幻觉参数。

### 3. 改造 `app/runs/tasks.py::run_chat`
- 改调 `answer_question_agentic`，传 `on_event` 回调，**循环每一步真实 emit**：
  - vector_search → emit searching；expand_entity → emit linking；模型反思决定再检索 → emit checking；生成最终答案 → emit writing → 终态 idle+answer。
- 这样前端像素房间真正跟着 Agent 多轮决策走（硬规则：动画来自真实事件）。
- **降级**：agent 抛错或 LLM 不支持 tool calling 时，回退调线性 `answer_question`，保证问答不挂。

## 五、硬规则与边界（必须守）

- **引用可追溯**：最终答案引用仍走 build_context 的 [n]↔Citation，Agent 版引用不得退化。证据池保留每个 chunk 的 chunk_id + provenance。
- **不绑厂商**：function calling 用 OpenAI-compatible 标准 tools 字段。**实测项目配的 LLM 端点是否支持 tool calling**，不支持则记录 + 启用降级。
- **token 控制**：工具结果回传只放引用 ID + 精简正文，不塞整段 chunk 反复留历史。
- **循环终止**：max_turns（默认 4）硬上限 + 自然终止（无 tool_calls）。
- **失败降级**：工具失败不崩，回传错误让模型决策；全程无证据返回「无法回答」。
- **装依赖**：本方案不需要新依赖（用现有 openai SDK）。如确需，先问大脑/用户。

## 六、测试与验证

- `backend/tests/qa/test_agent.py`（真实 LLM gate，未配置则 skip）：多轮决策、工具调用、引用可追溯、max_turns 终止、降级路径。
- `pytest tests/qa -q` 全过；`pytest -q` 全量不退化。
- 端到端：POST /api/chat 一个需多步检索的问题，看 Run 事件流出现**多轮** searching/checking（非固定三步），答案带可追溯引用。
- DEVLOG（backend/DEVLOG.md）：ReAct 循环原理、function calling 兼容性实测、token 控制、踩坑。

## 七、交接

本地 commit（写清做了什么），通知大脑分支名，大脑读 diff + 跑测试评审、合并。不自行合并 main。
