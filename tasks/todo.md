# Todo

## 个人知识图谱 GraphRAG Agent

目标：实现一个个人可用、简历可展示、公开 GitHub 可复现的知识图谱 Agent，支持技术论文、GitHub 仓库文档、产品业务需求文档的解析、Neo4j 图谱构建、GraphRAG 检索、引用追踪和清晰专业的前端工作台。

### 规划与范围确认

- [x] 明确服务对象为个人单用户。
- [x] 明确项目需要公开 GitHub。
- [x] 明确后续开发会结合 AI Coding + git worktree。
- [x] 明确 LLM 使用 OpenAI-compatible 接口。
- [x] 明确图谱存储直接使用 Neo4j。
- [x] 明确 Neo4j 使用 Docker 本地部署。
- [x] 明确样本文档优先覆盖技术论文、GitHub 仓库文档、产品业务需求文档。
- [x] 明确前端风格偏清晰专业。
- [x] 明确 PDF 解析需要落地。
- [x] 明确可以接入 GraphRAG 并做项目级微调。
- [x] 产出项目规划文档。
- [x] 将规划从版本/时间切分调整为完整落地范围和工程化开发路径。
- [x] 确认前端图谱可视化库。（Cytoscape.js）
- [x] 确认 PDF 解析库。（PyMuPDF）
- [x] 确认公开仓库名称和项目英文名。（graphrag-kg-agent）
- [x] 确认 OpenAI-compatible 服务商和默认模型名。（先用占位符，不绑定厂商）

### 项目基础设施

- [x] 初始化 Git 仓库结构。
- [x] 创建 backend / frontend / docs / samples / evals 目录。
- [x] 配置 `.gitignore`。
- [x] 配置 `.env.example`。
- [x] 编写 README 草稿。
- [x] 编写 Docker Compose，包含 Neo4j。
- [ ] 定义本地启动命令。（Neo4j 已就绪；前后端启动命令待对应模块实现后补充）

验证：

- [~] 新开发者按 README 可以启动 Neo4j、后端和前端。（Neo4j 已端到端验证通过：docker compose up + Cypher 实测；前后端待实现）
- [x] 密钥、缓存、运行数据不会被提交。（.gitignore 已覆盖，git status 已确认）

### 后端基础与配置

- [x] 初始化 FastAPI 应用结构。
- [x] 实现配置加载。
- [x] 实现日志。
- [x] 实现统一错误响应。
- [x] 实现健康检查接口。
- [x] 实现 OpenAI-compatible chat 客户端。（薄封装就位，真实调用待业务阶段验证）
- [x] 实现 OpenAI-compatible embedding 客户端。（同上）
- [x] 实现 Neo4j 连接管理。

验证：

- [x] 健康检查通过。（/health 与 /health/deps，pytest 2 passed）
- [~] 能成功调用 chat 和 embedding。（客户端就位；占位 key 下未做真实调用，待配置真实 LLM 后验证）
- [x] 能连接 Neo4j 并执行基础 Cypher。（/health/deps 返回 neo4j:ok，RETURN 1 通）

### 文档解析与切块

- [x] 实现 Markdown 解析。
- [x] 实现 txt 解析。
- [x] 实现 PDF 解析。
- [x] 实现 GitHub 仓库文档导入。
- [x] 实现 chunking 策略。
- [x] 记录 source metadata。

验证：

- [x] 样本文档能解析成稳定 chunk。（42 parsing 测试通过）
- [x] 每个 chunk 能追溯到来源文档。（raw_text[start:end]==chunk.text 断言守住偏移可追溯）
- [x] PDF 样本解析结果可用于检索和引用。（PyMuPDF，跨页偏移+页码，扫描页降级）

### Neo4j 图谱与向量索引

- [x] 定义 Neo4j 约束和索引。（document_id/chunk_id 唯一约束 + chunk 向量索引，awaitIndexes 等上线）
- [x] 写入 Document / Chunk。（确定性 chunk_id 幂等 MERGE，保留 provenance）
- [x] 写入 embedding。（批量同序，写入前维度校验）
- [x] 创建 Neo4j Vector Index。（cosine，维度走 EMBEDDING_DIM 配置）
- [x] 实现向量查询。（db.index.vector.queryNodes top-k，ChunkHit 带 provenance + score）
- [x] 写入 Entity / Relation。（已在「实体识别与关系抽取」板块实现：Entity 唯一约束 + RELATES）

验证：

- [x] Neo4j Browser 能看到文档、chunk、实体和关系。（文档/chunk 见 Neo4j 板块；实体/关系见抽取板块）
- [x] 向量检索能召回相关 chunk。（真实 embedding 端到端召回验证，10 集成测试连真实 Neo4j 通过）
- [x] 图谱中没有明显重复或孤立的异常数据。（chunk_id 幂等 MERGE 防重复，HAS_CHUNK 关联防孤立）

### 实体识别与关系抽取

- [x] 设计 LLM 结构化抽取 prompt。（JSON 模式，类型给候选不强制，含 json 字样单测锁定）
- [x] 实现实体抽取。
- [x] 实现关系抽取。
- [x] 实现 Mention 证据关联。（逐 chunk 抽取，MENTIONS 精确到 chunk）
- [x] 实现实体合并与去重。（归一名+类型精确合并；近义合并留待评估阶段）
- [x] 实现抽取失败重试和错误记录。（指数退避重试，单 chunk 失败跳过 + failed_chunks 统计）

验证：

- [x] 样本文档能稳定产生实体和关系。（真实 LLM 端到端：一篇文档抽 12 实体/10 关系）
- [x] 实体和关系能回溯到 chunk。（MENTIONS 边 + 每关系 evidence_chunk_id）
- [x] 抽取结果可以被前端和 GraphRAG 使用。（写入 Entity/MENTIONS/RELATES，22 测试通过）

### GraphRAG 检索与回答

- [ ] 接入并封装 GraphRAG 检索流程。
- [ ] 实现问题 embedding。
- [ ] 实现 top-k chunk 召回。
- [ ] 实现 entity neighborhood expansion。
- [ ] 实现 graph path 收集。
- [ ] 实现 rerank / filtering。
- [ ] 实现 GraphRAG context builder。
- [ ] 实现 answer generation。
- [ ] 实现 citation and path packaging。

验证：

- [ ] 用户问题能得到带引用答案。
- [ ] 答案能展示相关实体和关系路径。
- [ ] 引用能回到原始 chunk。

### Run 与事件流

- [ ] 实现 Run 记录。
- [ ] 实现 RunEvent 记录。
- [ ] 实现 SSE 或轮询事件接口。
- [ ] 映射文档解析事件。
- [ ] 映射实体和关系抽取事件。
- [ ] 映射图谱写入和索引事件。
- [ ] 映射检索和回答生成事件。
- [ ] 映射删除和重建事件。

验证：

- [ ] 前端能看到执行进度。
- [ ] 失败时能看到失败步骤和错误摘要。
- [ ] 像素 Agent 状态由真实事件驱动。

### 前端工作台

- [ ] 实现文档库。
- [ ] 实现上传 / 导入入口。
- [ ] 实现问答区。
- [ ] 实现答案和引用区。
- [ ] 实现图谱可视化。
- [ ] 实现运行事件时间线。
- [ ] 实现设置页。

验证：

- [ ] 用户可以在前端完成导入、索引、提问、查看引用和查看图谱。
- [ ] 页面布局不拥挤，重点信息清晰。

### 像素 Agent 动画

- [ ] 设计像素 Agent 基础形象。
- [ ] 实现 idle 状态。
- [ ] 实现 uploading 状态。
- [ ] 实现 parsing 状态。
- [ ] 实现 extracting 状态。
- [ ] 实现 linking 状态。
- [ ] 实现 indexing 状态。
- [ ] 实现 searching 状态。
- [ ] 实现 checking 状态。
- [ ] 实现 writing 状态。
- [ ] 实现 deleting 状态。
- [ ] 实现 rebuilding 状态。
- [ ] 实现 error 状态。
- [ ] 将动画状态接入 RunEvent。

验证：

- [ ] 每个核心操作都有对应动画。
- [ ] 动画不遮挡主工作流。
- [ ] 动画状态来自 RunEvent。

### 评估与质量保障

- [ ] 准备样本文档集。
- [ ] 准备问题与参考答案。
- [ ] 标注关键实体和关系。
- [ ] 编写 eval 脚本。
- [ ] 统计实体召回率。
- [ ] 统计关系可用率。
- [ ] 统计引用命中率。
- [ ] 统计明显幻觉率。
- [ ] 补充后端单元测试。
- [ ] 补充核心流程集成测试。

验证：

- [ ] 生成一份可复现的评估报告。
- [ ] 核心流程测试通过。
- [ ] README 说明如何运行评估。

### 公开展示与简历材料

- [ ] 完善 README。
- [ ] 绘制架构图。
- [ ] 准备演示脚本。
- [ ] 录制 GIF 或演示视频。
- [ ] 整理简历 bullet。

验证：

- [ ] 第三方能按 README 跑起来。
- [ ] 演示材料能完整展示文档入库、GraphRAG 问答、引用追踪、图谱可视化和像素 Agent 动效。

## Review

- 2026-06-16：将项目定位为个人知识图谱 GraphRAG Agent。确认 OpenAI-compatible 调用和 Neo4j 图谱存储，形成初始实现路线。
- 2026-06-16：根据用户反馈，规划文档移除对其他项目文档的引用，弱化字段清单为概念模型；确认公开 GitHub、git worktree、样本文档领域、清晰专业前端、Neo4j Docker、本地 PDF 解析和 GraphRAG 接入策略。
- 2026-06-16：根据用户反馈，规划从“版本/时间切分”调整为“完整落地范围 + 标准工程化开发路径”，避免后续实现时反复争论临时范围边界。
- 2026-06-17：敲定 4 项待确认决策（PDF=PyMuPDF、可视化=Cytoscape.js、LLM=占位符不绑厂商、仓库名=graphrag-kg-agent）。完成项目基础设施：迁入新仓库并 git init + 推送 GitHub（公开）、配置 `.gitignore`、创建 backend/frontend/samples/evals 目录骨架、编写 `.env.example`、`docker-compose.yml`（Neo4j 5.26）、README 草稿。本机未装 Docker，Neo4j 端到端验证待装 Docker 后进行。
- 2026-06-17：装好 WSL2 + Docker Desktop，docker compose 拉起 Neo4j 5.26 并用 cypher-shell 实测连通，README 的「一键起 Neo4j」端到端可复现。
- 2026-06-17：完成后端 FastAPI 骨架（首次试用「总指挥 + 后台 worktree 执行代理」工作流）：config/clients/routers 分层、pydantic-settings 读 .env、lifespan 管理 Neo4j 驱动、统一错误响应、/health 与 /health/deps 双探针。pytest 2 passed，/health/deps 返回 neo4j:ok。主窗口 review 通过后合并，清理 worktree 时发现并停掉了代理残留的 uvicorn 进程（经验：子代理启动的后台进程需主动回收）。
- 2026-06-17：「大脑 + 工人」多窗口并行首次完整跑通。后端 worktree（feat/backend）做文档解析与切块、前端 worktree（feat/frontend）做工作台脚手架，并行推进。大脑 review 发现并打回后端 PDF 同页重复段落的偏移 bug（违反偏移可追溯硬规则，测试未覆盖、靠读代码发现），后端修复并加回归测试（42→44 全过）。前端因基线落后于协作约定提交，先 `git merge main` 同步再合（避免误删 CLAUDE/AGENTS 协作约定）。两条经 review 后由大脑按「先后端后前端」顺序合入 main，全量回归通过。
- 2026-06-18：复用 feat/backend worktree 完成「Neo4j 图谱与向量索引」（Document/Chunk + embedding + 向量检索；Entity/Relation 留给抽取板块）。新增 app/graph：schema（约束+向量索引+awaitIndexes 防 51N63）、writer（确定性 chunk_id 幂等 MERGE，保留 provenance）、embedding（批量同序）、search（原生向量索引召回带 score）；schema 初始化接入 lifespan（失败仅告警）；EMBEDDING_DIM 走配置。10 集成测试真连 Neo4j 且 test_ 前缀自清理不污染共享库，全量 54 passed。大脑 review 通过后合并。流程小插曲：工人首次「执行完毕」时忘 commit，提醒后补交（再次印证交接信号=本地 commit）。
- 2026-06-18：复用 feat/backend 完成「实体识别与关系抽取」。新增 app/extraction：逐 chunk 调 LLM（JSON 模式，response_format 透传且向后兼容）抽实体/关系、文档内归一名+类型精确合并去重、写入 Entity/MENTIONS/RELATES。每关系带 evidence_chunk_id、Mention 精确到 chunk（引用可追溯）；业务关系统一 :RELATES 类型作属性（遵守决策边界）；关系两端解析不到即丢弃防脏边；单 chunk 失败跳过+指数退避重试；Entity 加唯一约束并强制带 document_id（保共享库清理）。真连 Neo4j+真实 LLM 测试，全量 76 passed（main 上真实 LLM 测试因未配 key 而 skip）。同步勾选上一板块遗留的「写入 Entity/Relation」。
