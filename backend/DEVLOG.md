# 后端学习记录（DEVLOG）

## 2026-06-17 后端 FastAPI 骨架搭建

- 做了什么：搭起 `backend/` 的 FastAPI 应用骨架——配置、日志、统一错误、Neo4j/LLM 客户端薄封装、健康检查路由与测试，跑通 `/health` 与 `/health/deps`。

- 这是什么：
  - **FastAPI** 是一个 Python Web 框架，用来把函数暴露成 HTTP 接口。你写一个普通函数，加个装饰器（如 `@router.get("/health")`），它就变成一个网页地址能访问的接口，并自动帮你做参数校验、生成文档。
  - **pydantic-settings** 是“配置读取器”。它把 `.env` 文件里的环境变量（如 `NEO4J_PASSWORD=...`）自动映射成一个 Python 对象的字段，省去手写 `os.getenv` 和类型转换，还能集中管理。
  - **lifespan** 是 FastAPI 的“开机/关机钩子”。应用启动时跑一段代码、关闭时跑另一段。我们用它在启动时建好 Neo4j 连接、在关闭时干净地断开，避免连接泄漏。
  - **Neo4j driver（驱动）** 是连接 Neo4j 图数据库的客户端对象。它内部维护一个连接池，整个应用共享一个 driver 就够了，不必每次查询都重新连。

- 为什么需要：这是后端的“地基”。后面所有功能（文档解析、抽取、图谱构建、检索问答）都挂在这套骨架上。先把“怎么读配置、怎么连数据库、出错怎么统一返回、怎么自检健康状态”这几件事固定下来，后续写业务逻辑时就不用反复操心基础设施。`/health` 还能让部署后一眼确认“服务活着没”，`/health/deps` 确认“依赖（Neo4j/LLM）通不通”。

- 为什么这么做（分层理由）：
  - **config / clients / routers 分开**：配置只管“从哪读、读什么”；clients 只管“怎么和外部系统（Neo4j、LLM）说话”；routers 只管“对外暴露哪些接口”。三者职责单一，改一处不牵连另两处——比如以后换 LLM 厂商，只动 `clients/llm.py`，路由和配置都不用碰。
  - **配置全走环境变量、零硬编码**：密钥、地址、模型名都从 `.env` 读，代码里不写任何真实值。这样公开仓库不会泄密，换环境也只改 `.env`。`get_settings()` 用 `lru_cache` 缓存，保证全程只读一次 `.env`、只有一个配置实例。
  - **`/health` 与 `/health/deps` 拆成两个**：前者绝不依赖外部、永远通，用于“进程活着吗”；后者探测 Neo4j 和 LLM，且把任何失败**降级成文本**（如 `"error: ..."`）而不是抛 500——探针自己不能因为依赖挂了就崩，否则没法用它来诊断。
  - **统一错误结构**：所有异常都包成 `{"error": {"type", "message"}}`，前端拿到的错误格式永远一致，不用对每种报错单独适配。
  - **LLM 用 OpenAI-compatible 接口**：用 `openai` 库 + 自定义 `base_url`，这样任何兼容 OpenAI 协议的服务商都能接，不锁死单一厂商。`is_configured()` 通过识别 `.env.example` 里的占位标记（`your-` / `please-change`）判断是否填了真实值，骨架阶段不真的去调 LLM，避免占位 key 报错。

- 踩了什么坑：
  - **neo4j 6.x 的连通性探测写法**：本机装的是 neo4j 6.2.0。早期教程里 `driver.verify_connectivity()` 在不同版本行为/可用性有差异，这里直接用更稳的 `driver.execute_query("RETURN 1")`——能跑通就说明连接、认证、查询全链路 OK，语义比单纯握手更可靠。
  - **driver 是“懒连接”**：`GraphDatabase.driver(...)` 这一步并不会立刻连数据库，真正建连接发生在第一次执行查询时。所以 lifespan 里建 driver 不会因为 Neo4j 没起来而失败，连不上的暴露点统一落在 `/health/deps` 的 `execute_query`，正好被它的 `try/except` 接住降级——测试因此不依赖真实 Neo4j 也能过。
  - **worktree 没有 .env**：当前在隔离的 git worktree 里工作，仓库根没有 `.env`。按要求从 `.env.example` 复制了一份测试用 `.env`（把 `NEO4J_PASSWORD` 改成本机 Neo4j 容器的密码 `TestPass12345`，LLM 字段保持占位），验证完毕。`.env` 已被 `.gitignore` 忽略，不会误提交。
