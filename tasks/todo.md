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

- [x] 接入并封装 GraphRAG 检索流程。（app/qa pipeline，编排控制权在项目内）
- [x] 实现问题 embedding。
- [x] 实现 top-k chunk 召回。（复用 graph.search_chunks）
- [x] 实现 entity neighborhood expansion。（MENTIONS→RELATES 扩 1 跳，手写 Cypher）
- [x] 实现 graph path 收集。（RelationPath 带 evidence_chunk_id）
- [x] 实现 rerank / filtering。
- [x] 实现 GraphRAG context builder。（chunk 编 [n] 角标 ↔ Citation）
- [x] 实现 answer generation。（LLM 带引用答案）
- [x] 实现 citation and path packaging。（只留答案真实引用的角标 + /api/chunks 反查）

验证：

- [x] 用户问题能得到带引用答案。（POST /api/chat，真实 LLM gate 测试通过）
- [x] 答案能展示相关实体和关系路径。（RelationPath 单列入上下文）
- [x] 引用能回到原始 chunk。（Citation.chunk_id + /api/chunks/{id} 反查原文）

### 文档上传与文档库 API（A 板块）

- [x] 实现 POST /api/documents 同步上传入库链路。（parse→embed→ingest→extract）
- [x] Document 节点落状态字段。（name/source_type/parse_status/index_status/chunk_count）
- [x] 实现 GET /api/documents 文档列表。（直查图库）
- [x] 实现 GET /api/documents/{id} 单文档详情。
- [x] 上传大小上限走配置。（MAX_UPLOAD_MB=10）
- [x] 临时文件 try/finally 清理。

验证：

- [x] 上传 md/txt 同步返回结果摘要，documentId 稳定。（camelCase alias 对齐前端契约）
- [x] 重复上传同一文件 chunk/entity 不翻倍。（幂等硬要求，双重断言：chunkCount + 图库 Chunk 节点数）
- [x] 不支持的扩展名返回 400，超大文件返回 413。
- [x] 上传后 /api/chunks/{id} 能反查（端到端贯通）。
- [x] GET /api/documents 返回的列表含状态字段。
- [x] main 上全量 100 passed + 5 skipped（真实 LLM 测试因 main 无 key 正确 skip）。

### Run 与事件流

> A 板块已交付文档上传同步链路（见下方「文档上传与文档库 API」）；本节为 B 板块（异步 Run + SSE）。

- [x] 实现 Run 记录。（app/runs/models.py：Run + RunKind[ingest/chat/delete] + RunStatus）
- [x] 实现 RunEvent 记录。（stage 锁定前端 12 枚举 + status + message + answer 终态 payload）
- [x] 实现 SSE 或轮询事件接口。（/api/runs/{id}/events/stream + /events 历史 + GET /api/runs/{id}）
- [x] 映射文档解析事件。（run_ingest：uploading→parsing→extracting→indexing→done）
- [x] 映射实体和关系抽取事件。（同上 extracting/indexing 阶段）
- [x] 映射图谱写入和索引事件。（ingest_document + extract_and_ingest 各对应阶段）
- [x] 映射检索和回答生成事件。（run_chat：searching→checking→writing→done，终态带 answer）
- [x] 映射删除和重建事件。（run_delete：deleting→done；rebuilding 暂未触发，留作扩展）

验证：

- [x] 前端能看到执行进度。（SSE 流历史回放 + 实时推送 + 终态关闭）
- [x] 失败时能看到失败步骤和错误摘要。（后台任务全程 try/except，失败 emit error + status=failed，SSE 流关闭）
- [x] 像素 Agent 状态由真实事件驱动。（AgentRoom 接入 useRunEvents，currentStage 由 SSE 派生）

### 前端工作台

- [~] 实现文档库。（LibraryView 已接真实 GET /api/documents；上传/删除走 SSE runId 异步流；契约层已对齐）
- [~] 实现上传 / 导入入口。（POST /api/documents 起 Run + SSE 订阅，终态刷新列表；导入仓库占位已删，无后端支持）
- [x] 实现问答区。（WorkbenchView 接真实 /api/chat + SSE）
- [x] 实现答案和引用区。（CitationPanel 真实 Citation + chunkId 反查）
- [x] 实现图谱可视化。（GraphView 接真实 /api/graph/*，字段映射收口在 api/graph.ts）
- [x] 实现运行事件时间线。（RunEventTimeline 接真实 SSE via useRunEvents）
- [x] 实现设置页。（SettingsView 接 /health/deps 展示 Neo4j/LLM 连通状态）

验证：

- [x] 用户可以在前端完成导入、索引、提问、查看引用和查看图谱。（全链路接真实 API）
- [x] 页面布局不拥挤，重点信息清晰。（布局 A + 精细化设计系统，build 通过）

### 像素 Agent 动画

> 路线调整：放弃精细角色逐帧动画，改 ZCodeRoom 式「深紫房间 + 极简悬浮小人 + 场景道具叙事」（AgentRoom 组件）。小人本体几乎不动，状态靠头顶气泡 + 周围道具表达。

- [x] 设计像素 Agent 基础形象。（box-shadow 像素法极简小人，对齐 ZCodeRoom + 蓝靛卫衣 + 眼镜）
- [x] 实现 idle 状态。（悬浮 bob + ☕ 气泡）
- [x] 实现 uploading 状态。（文档飞入 + 📥）
- [x] 实现 parsing 状态。（文档翻页 + 📄）
- [x] 实现 extracting 状态。（标签弹出 + 🏷️）
- [x] 实现 linking 状态。（连线生长 + 🔗）
- [x] 实现 indexing 状态。（档案柜抽屉 + 🗂️）
- [x] 实现 searching 状态。（放大镜扫描 + 🔍）
- [x] 实现 checking 状态。（放大镜校对 + ✓）
- [x] 实现 writing 状态。（纸条吐出 + ⌨️）
- [x] 实现 deleting 状态。（碎纸机 + 🗑️）
- [x] 实现 rebuilding 状态。（复印机 + 🔄）
- [x] 实现 error 状态。（红光闪 + 小人抖动 + ⚠️）
- [x] 将动画状态接入 RunEvent。（AgentRoom 消费 useRunEvents 的 currentStage，红线守住）

验证：

- [x] 每个核心操作都有对应动画。（12 状态全覆盖，StyleGallery 预览页可一览）
- [~] 动画不遮挡主工作流。（嵌侧栏不占主区；道具遮挡小人等细节瑕疵待后续微调）
- [x] 动画状态来自 RunEvent。（currentStage 由真实 SSE 派生，devControls 仅开发预览）

### 评估与质量保障

- [x] 准备样本文档集。（4 篇：agents/api-needs/parsing-design/planning，放 samples/）
- [x] 准备问题与参考答案。（evals/ground_truth.jsonl，每篇含 questions + answer_keywords）
- [x] 标注关键实体和关系。（ground_truth.jsonl 含 entities/relations 标注）
- [x] 编写 eval 脚本。（evals/run_eval.py，可复现，LLM 随机性已说明）
- [x] 统计实体召回率。（实测 57.1%，未达 70% 目标——已诚实记录，待抽取优化）
- [x] 统计关系可用率。（实测 100%）
- [x] 统计引用命中率。（实测 100%）
- [x] 统计明显幻觉率。（实测 16.7%，达标 ≤20%；含待人工复核清单）
- [~] 补充后端单元测试。（新增 test_tasks 覆盖 run_chat；其余模块已有覆盖）
- [x] 补充核心流程集成测试。（test_tasks 覆盖异步问答任务）

验证：

- [x] 生成一份可复现的评估报告。（evals/report.md + docs/evaluation.md 指标定义）
- [x] 核心流程测试通过。（main 全量 119 passed + 1 skip）
- [x] README 说明如何运行评估。（README 评估章节）

### 多轮对话记忆（B 方案：对话进图谱）

> 规划：大脑与用户逐条确认定板。拆前后端两份独立交接清单（冻结 API 契约解耦并行），分别交 feat/backend、feat/frontend 执行。

- [x] 后端：会话/消息数据层（conversations 模块 + schema 扩展 + embed_texts 抽取）。
- [x] 后端：Agent 接收历史（history 参数）+ run_chat 读历史/写回本轮 + 降级路径同步。
- [x] 后端：会话 CRUD API（POST /api/chat 加 conversationId + /api/conversations 四端点）。
- [x] 前端：类型（conversation.ts）+ API 封装（conversations.ts）。
- [x] 前端：WorkbenchView 多会话状态管理（conversationId + 切换/回看/刷新恢复）。
- [x] 前端：会话侧边栏组件 + 三列布局调整 + 无障碍不退化。
- [x] 端到端：契约对齐 + 测试不回归（后端 140 passed/6 skip；前端 typecheck/build 通过）。

验证：

- [~] 同会话连续追问能正确指代上文（答案带 [n] 角标）。【代码层 review + 单测覆盖（test_with_history_uses_context 真实 LLM 用例因配额 403 未能实跑，逻辑经回源码核实正确）；待配额恢复或换 key 做一次真实多轮手测】
- [~] 会话隔离：A 会话历史不串到 B 会话。【按 conversation_id 隔离，get_messages 严格按会话查询；逻辑核实，待真实手测】
- [~] 刷新页面会话列表/历史可恢复。【后端落 Neo4j 持久化 + 前端 listConversations/getConversation 接真实；逻辑核实，待真实手测】
- [x] Neo4j Browser 能查到 Conversation/Message 节点；message_embedding 索引建好（test_store 真连 Neo4j 通过）。
- [x] 记忆窗口：超 6 条老历史不进 LLM、但仍在图谱（_MAX_HISTORY_TURNS=6 + get_messages limit，test_get_messages_limit_window 覆盖）。
- [x] 现有基线不回归（126→140 passed）+ 新增 14 个 conversations 测试全过。

### 公开展示与简历材料

- [ ] 完善 README。
- [ ] 绘制架构图。
- [ ] 准备演示脚本。
- [ ] 录制 GIF 或演示视频。
- [ ] 整理简历 bullet。

验证：

- [ ] 第三方能按 README 跑起来。
- [ ] 演示材料能完整展示文档入库、GraphRAG 问答、引用追踪、图谱可视化和像素 Agent 动效。

### 体验升级批次（2026-07-03 签发，规格见 docs/superpowers/specs/2026-07-03-experience-upgrade-design.md）

后端工人（feat/backend，清单 tasks/handoff-backend-extraction-quality.md）：

- [x] B1 抽取 prompt 重写（封闭类型集/排除清单/枚举展开/中英混合 few-shot）
- [x] B2 归并 key 去 type
- [x] B3 Entity 写 mentionCount（不做硬过滤）
- [x] B4 图谱 API 度数降序 + degree/mentionCount 字段
- [x] B5 评估扩全量 4 篇 + 未匹配清单（验收：实体召回 ≥ 70%）
- [x] B6 问答输出格式指示（Markdown 分段，配合前端渲染）

前端工人（feat/frontend，清单 tasks/handoff-frontend-answer-graph-agentroom.md，F1→F2→F3 串行）：

- [x] F1 回答区 Markdown 化 + 引用角标内联可点（末尾保留汇总行）
- [x] F2 图谱展示分级降噪（fcose 布局/度数分级/隐藏孤立节点默认开）
- [x] F3 AgentRoom 生命感（行为队列状态机 + idle 随机剧本 + 工作循环编排）+ 视觉升级（ui-ux-pro-max / frontend-design 技能）

依赖已由大脑装入 main：react-markdown / remark-gfm / cytoscape-fcose（前端，0 漏洞）。

批次遗留（非阻断，后续排期）：

- [ ] 评估分句器 Markdown 感知化（B6 Markdown 输出致幻觉指标假阳性 16.7%→26.5%，逐条核查 0 条真编造；分句器不应把 Cytoscape.js 的点号当句界）
- [ ] backend/app/extraction/models.py 陈旧注释（entity_id 格式已去 type）+ writer/chat 测试统一新 entity_id 格式
- [ ] evals 汇总口径补说明（87.7% 为标注加权池化值，宏平均 86.6%）
- [ ] F1 引用式链接定义 `[1]: url` 与角标碰撞（罕见）、引用芯片 aria-label 补文档来源
- [ ] F2 搜索命中被隐藏孤立节点时的反馈、自环/重边度数口径、toggle 重排 randomize 跳变
- [ ] F3 StyleGallery 预览微动画措辞、非 idle 初始一帧闪跳（useLayoutEffect）、sceneMap.detail 死字段

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
- 2026-06-18：双线并行收获两个板块。后端 feat/backend 完成「GraphRAG 检索与回答」：app/qa 编排 向量召回→rerank→实体邻域扩展(MENTIONS/RELATES 1跳)→上下文组装([n]角标↔Citation)→LLM 带引用答案，新增 /api/chat 与 /api/chunks/{id}，Answer/Citation 用 camelCase alias 对齐前端契约，只保留答案正文真实出现的角标，关系带 evidence_chunk_id，全量 94 passed。前端 feat/frontend 完成 P1/P2/P3：精细化 token 体系 + 7 个共享 UI 基件 + dev 预览页、工作台/文档库/图谱探索三视图(mock + Cytoscape)、引用面板角标点击滚动定位 + chunkId 反查，mock 严格对齐 src/types，typecheck/build 通过，像素小人保持 idle 待用户亲调。两条经大脑 review（含核查 todo.md 未被前端误改、前后端 Citation 契约已对齐）后按先后端后前端顺序合入 main。
- 2026-06-22：大脑 review 后端窗口「文档/图谱 API + Run 事件流」合并大方案，裁决拆 A/B 两个独立交付（先 A 后 B），并明确 /api/chat 异步化（用户确认要做）和 DELETE 语义归 B 板块。后端按裁决完成 A 板块「文档上传入库 API + Document 状态字段」：POST /api/documents 同步跑完整链路（parse→embed→ingest→extract），Document 落 name/source_type/parse_status/index_status/chunk_count 状态字段（writer 顺手 SET），GET 列表/详情直查图库，camelCase alias 对齐前端，MAX_UPLOAD_MB 走配置，try/finally 清理临时文件。document_id 沿用 parse_file 内部稳定 id（规避 chunk_id 幂等破坏），幂等测试双重断言（chunkCount + 图库 Chunk 节点数）。main 上全量 100 passed + 5 skipped。注：feat/backend worktree 因配了真实 LLM key，chat/extraction 真实 LLM 测试因配额耗尽(403)而失败，但属环境问题非代码缺陷（A 未碰 chat 代码），main 上无 key 正确 skip 不受影响——既有测试设计可加 is_configured gate，留待后续。A 合并入本地 main，待网络恢复推送。
- 2026-06-22：后端 feat/backend 完成 B 板块「Run/事件流 + SSE + 异步化 + 图谱查询 API」。新增 app/runs：models（Run/RunEvent + Stage 12 枚举锁定前端契约 + RunStatus + RunKind[ingest/chat/delete]）、store（内存注册表 + asyncio.Queue 订阅 + 历史回放 + 终态关闭，不持久化对齐简单优先）、tasks（run_ingest/run_chat/run_delete 后台任务，全程 try/except + 失败 emit error 防 SSE 流卡死）。新增 routers/runs（SSE stream + /events 历史兜底 + GET /{id}，含心跳保活）、routers/graph（实体列表带边悬空过滤、1跳邻域去重、模糊搜索）。异步化：POST /api/documents 改返回 {runId,documentId}，POST /api/chat 改返回 {runId} 终态事件带 answer（方案 a，省往返），DELETE /api/documents/{id} 异步删（语义按裁决：删 Document+Chunk+MENTIONS，Entity 靠 MENTIONS 孤立性判定保留共享）。采纳上轮标记的既有问题改进：chat 真实 LLM 测试重构为 mock + seed，不再因配额失败。main 上全量 117 passed + 1 skipped（extraction 真实测试因 main 无 key 正确 skip）。契约变化已记录，前端切真实时需按新契约（runId + SSE 订阅）接入。
- 2026-06-22：前端 feat/frontend 完成「契约层改造对齐 B 板块异步 + SSE」（大脑拆分的第一轮，像素小人留下一轮亲调）。新建 api/sse.ts（subscribeRunEvents：EventSource 封装，终态 succeeded/failed 双保险 close，payload 严格校验 stage/status 枚举，BASE_URL 复用 client.ts），改造 useRunEvents（接 runId 参数 + 订阅真实 SSE + 切换重置 + 红线保留：currentStage 只从事件派生）。类型对齐后端：RunEventStatus 改 running/succeeded/failed、RunEvent 加 answer/timestamp_ms（采纳下划线，和后端 by_alias 一致）、Citation 加 documentId。业务场景改造：LibraryView 上传用原生 fetch+FormData（避开 apiFetch 强制 JSON content-type，工人自行想到的正确细节）→ 起 Run → 订阅 → 终态刷新，isBusy 防重复，删假按钮（导入仓库/重建索引无后端支持）；WorkbenchView 问答用户消息立即显示、终态落 agent 消息、引用展示"最近一条"语义；Timeline status 映射改对。GET 类（文档列表/图谱/chunks）保持 apiFetch 不变。mock SSE 未做（直连真实后端更简单，大脑倾向一致）。typecheck 零错误，build 成功（653KB chunk 警告是 Cytoscape 体积，非阻塞）。像素小人保持 idle 占位，未擅动。
- 2026-06-24：像素 Agent 路线转向并落地。原精细 CSS 角色（PixelAgent）观感不达标（圆角化、比例失调、细节糊），且 AI 画精细角色一致性差——遂改 ZCodeRoom 式「深紫房间 + 极简悬浮小人 + 场景道具叙事」：小人弱化为 box-shadow 像素法色块（对齐 ZCodeRoom 配色 + 蓝靛卫衣 + 眼镜），状态靠头顶气泡 + 周围道具（碎纸机/放大镜/翻页等）表达。大脑先出 HTML 原型验证方向 + 写交接文档（frontend/docs/agent-room-*.md），feat/frontend 落地为 AgentRoom 组件并用 box-shadow 单 div 法优化性能、加常驻桌椅场景、StyleGallery 加 12 状态预览。currentStage 仍由真实 RunEvent 驱动（红线）。大脑 review 通过 + 用户审美验收通过（道具遮挡小人等细节瑕疵记录待后续微调），删除旧 PixelAgent，合并入 main。注：GitHub 推送暂缓，仅本地同步。
- 2026-06-24：双线并行收两个板块。后端「评估与质量保障」：4 篇样本 + ground_truth 标注 + run_eval.py + report.md + docs/evaluation.md，量化四指标（解析100%/关系可用100%/引用命中100%/幻觉16.7% 达标，实体召回57.1% 未达70% 已诚实记录待优化）；评估中抓出 B 板块 run_chat 真 bug（误传 question 字符串给 search_chunks 未 embed + Answer 构造不存在字段），改为复用已验证的 answer_question，加 test_tasks。前端「真实 API 接入收尾」：GraphView 接 /api/graph/*（字段映射层 api/graph.ts 收口后端↔前端命名差异）、SettingsView 接 /health/deps、移除 mockGraph。至此前端工作台与像素 Agent 全链路接真实 API。大脑 review 通过后先后端后前端合入 main，全量 119 passed。GitHub 推送仍暂缓。
- 2026-06-27：项目从「线性 GraphRAG」升级为名副其实的 **Agentic RAG**。诊断出原 answer_question 是固定 pipeline（无推理循环/自主决策/记忆），经调研定技术路线（纯自研 while 循环 + OpenAI 原生 function calling，不引 LangGraph——单 agent+内部工具场景主流共识，保留编排控制权）。新增 app/qa/agent.py：ReAct 检索-反思循环，LLM 自主在 vector_search/expand_entity 间自选、判断证据够不够、不够换查询再检索；双终止（无 tool_calls / max_turns 兜底）；证据池保留 provenance，引用仍走 build_context [n]↔Citation 不退化；on_event 回调让 run_chat 循环每步真实 emit RunEvent（前端像素房间跟着多轮决策走）；端点不支持 tool calling 时降级线性 pipeline。扩展 llm.chat_with_tools，保留 answer_question 作降级兜底+评估基线。125 passed（test_agent 真连 LLM 验证多轮/终止/兜底/事件，function calling 兼容性实测通过）。单窗口 feat/backend 串行实现（任务内部强依赖链，不宜拆多窗口），大脑 review 通过后合并。
- 2026-06-28：PR 审计（6 并行子代理 + 主审回源码复核）→ 大脑逐条核实属实后拆前后端整改清单。后端完成 B1-B15：必修(sse-starlette补全+锁版本、API Key鉴权中间件[空跳过/health豁免]、LLM超时+重试+空choices防护、统一启动命令去D:\绝对路径)、正确性(BackgroundTasks用 asyncio.to_thread 异步化+call_soon_threadsafe 跨线程安全 emit 恢复SSE实时性、RunStore TTL GC、CORS限定来源、RunEvent timestampMs 契约统一+删冗余alias、embedding维度运行时校验、500不泄露内部)、加分(RunEvent tool_*/token_usage可观测、问答Semaphore限并发、PDF页数上限)。B10独立测试索引名被 Neo4j「单property单向量索引」限制否决，退回 teardown+lifespan维度校验兜底（DEVLOG记录决策）。126 passed，大脑逐条回源码 review 通过合并。前端审计整改（无障碍7项+响应式+契约协同）待后端契约就绪后动工。
- 2026-06-29：规划升级方向。用户提出参考 LLM Wiki / GBrain / Loop Engineering 等近期概念，让 Archigraph 从「静态知识消费工具」升级为「辅助开发者更新个人知识库、驱动 Agent 协助自进化」的方向。大脑联网调研上述概念（共同内核：Agent 需要可累积、可结构化、能进化的外挂大脑），与用户多轮澄清后校准诉求：① 不要求系统自进化，而是「协助自进化」（人搜集→Agent 提取关系要点→人据此更新）；② 联网搜索与跨文档对比属后续能力，本次不做；③ **对话记忆是最需要补的能力**。先定方案 B（对话进图谱）落地：对话存 Neo4j（Conversation/Message 节点）、问答都向量化、近期历史注入 LLM（滚动窗口 6 条）、多会话+侧边栏 UI。大脑派 3 个并行子代理摸透后端问答链路/图谱写入模式/前端对话 UI，逐条确认设计决策（历史注入方式、存储位置、会话 UI 形态、记录内容、是否向量化），产出冻结 API 契约并拆前后端两份独立交接清单（handoff-{backend,frontend}-conversation-memory.md），由用户通知两窗口并行执行。待执行完成后大脑 review 合并。
- 2026-06-30：多轮对话记忆（B方案）落地完成，前后端双线并行 + 大脑 review 合并。**后端 feat/backend**：新增 app/conversations（Conversation/Message 节点 CRUD + message_embedding 向量索引，message_id=conv_id#turn_index 幂等 MERGE，turn_index 自增）；schema 加 2 约束 + 消息向量索引，main.py 维度兜底参数化覆盖 chunk+message 两索引；抽取 embed_texts（embed_chunks 复用，消息向量化复用）；agent/pipeline 加 history 参数（近期历史注入 [system,*history,user]），prompt 守引用红线（不得仅凭历史记忆作答）；run_chat 接 conversation_id → 读历史注入 → 写回本轮 user/agent 两条消息（问答各 embed 一次）；chat 路由同步解析会话 id（首问 create_conversation 在主线程，保 HTTP 响应立即返 id）+ 新增 /api/conversations 四端点。新增 14 测试全过（store/api/agent/tasks，含 turn_index 自增/幂等/citations 往返/注入窗口/列表降序/run_chat 主降级失败三路径）。**前端 feat/frontend**：新增 ConversationSidebar（会话列表/新建/切换/删除+二次确认，无障碍规范 role/aria/键盘可达/对话框）+ types/conversation + api/conversations；WorkbenchView 多会话状态管理（conversationId + 终态只清 chatRunId 不清会话[关键正确] + 切换回灌历史 toChatMessages 复用渲染）+ 三列布局 + 空态引导。**大脑 review**：逐条回源码核实（幂等/同步解析会话 id/history 默认 None 保现有测试不回归/降级带 history/维度兜底覆盖两索引/测试隔离 conv_test 前缀），跑测试 140 passed/6 skip（6 个真实 LLM 用例因 feat/backend worktree 配真实 key 配额耗尽 403，main 无 key 正确 skip，与 2026-06-22 同款环境问题非代码缺陷），前端 typecheck 零错误/build 通过。**大脑收尾**：发现前端遗留 USE_MOCK=true 未切真实（合并阻碍，会导致会话功能跑内存 mock 假数据），由大脑在 feat/frontend 改 false + 删 mock 段 + 补 DELETE 错误结构解析，重跑 typecheck/build 通过。按「先后端后前端」顺序合并 main（前端只动 frontend/、后端只动 backend/，无冲突），合并后 main 后端 140 passed/6 skip 无回归、前端 build 通过。handoff 交接清单文档美化（代码块加空行）随合并带入。**已知后续项**：① 真实多轮手测（验收 1/2/3 待配额恢复或换 key 实跑，代码逻辑已核实）；② turn_index 并发隐患（_NEXT_TURN 与 _ADD_MESSAGE 非原子，受 Semaphore+单用户串行写保护不撞，幂等 MERGE 保不翻倍，记录在案）；③ 会话标题取首问前 30 字，未来可让 LLM 生成。GitHub 推送本次执行（之前几轮暂缓）。
- 2026-07-03：「长任务 SSE 终态事件丢失」**澄清为非 bug**。用户实测确认终态事件最终会正常到达浏览器——此前"进度停在抽取阶段、列表不刷新"只是实体抽取逐 chunk 调 LLM 耗时数分钟，每次诊断都没等到任务真正结束就误判"丢失"，SSE 链路前后端均无缺陷。多轮"修复"（后端 sleep 延迟关闭、前端 onerror 历史兜底、放行原生重连 + seq 去重）此前已全部回退，代码无容错/调试残留。本次收尾：更正 frontend/DEVLOG.md 与 backend/DEVLOG.md 两条误记条目、删除过时交接文档 tasks/handoff-sse-terminal-event-bug.md、新增 lessons L8（诊断「事件没到」前先确认「事件该到的时刻是否已过去」，对照实验须同条件）。保留项：后端 RunEvent.seq 字段（事件基础设施，日后断线重连去重可用）、「刷新列表/刷新图谱」按钮（转为低频手动刷新入口，不再是 bug 绕过手段）。
- 2026-07-03：大脑 review 合并 feat/frontend 两个修复提交（merge d3e0eef）。**a93e2b0 慢一拍竞态修复**（质量高，直接合入）：useRunEvents 把清空事件挪到渲染期（React 官方"渲染期随输入调整 state"模式），根修「问答显示上一轮回答/上传要第二次才生效」——旧代码重置被 `if (!runId) return` 挡住，runId→null 时事件残留，下轮 Run 的终态 effect 读到旧事件误当本轮结果。**a087a94 SSE 兜底 + 刷新按钮**（有保留合入）：onerror 查 /events 历史补投终态的兜底，虽源于已澄清的误诊（07-01 提交，早于误诊结论），但对真实断线（网络抖动/服务重启）是有效防御，评审定性为防御性容错保留；图谱刷新按钮与 main 0cbaff0 重复，合并时去掉分支实现。**合并时修正两处**：sse.ts 头注释按误诊结论重新定性（不再声称"修终态丢失 bug"）；补 disposed 退订守卫——原 closed 标志的注释声称能屏蔽卸载后的迟到回调但实现未检查，迟到的兜底 fetch 会把旧 Run 终态泄漏进新 Run（恰是 a93e2b0 修的那类串味）。DEVLOG 冲突按时间序保留双方条目，并订正「sse.ts 无容错残留」表述与实际合并结果一致。前端 tsc 验证通过；main 工作区未提交批次经 stash 往返无损恢复。
- 2026-07-03：体验升级批次双线收官（merge 6237527 后端 + 708430f 前端）。**后端 B1-B6**：抽取 prompt 重写（封闭类型集/排除清单/枚举展开/中英混合 few-shot）+ 归并去 type（Counter 多数决，并列取先见，确定性核验）+ mention_count + 图谱 API 度数降序（degree=RELATES+MENTIONS，孤立保留、HAS_CHUNK 不误算）+ 评估扩全量 4 篇：**实体召回 57.1%→87.7%（池化）/86.6%（宏平均），四篇最低 78.6%，≥70% 硬指标稳达**。**前端 F1-F3 + R1 五项必修**：回答区 react-markdown + remark AST 角标插件（代码区免疫污染，正解替代字符串预处理）+ 消息级 React.memo 记忆化；图谱 fcose 布局 + 度数三档分级 + 隐藏孤立默认开（丢高亮/空白提示两缺陷修复）；AgentRoom 行为队列状态机（idle 加权随机剧本 + 工作 stage 循环编排 + 中断即转保留）+ 顺手修复 roomScenes.css 死选择器（全局裸类名命不中 CSS Module 哈希，linking/searching/error 道具动画从未生效过）+ 系统性布光视觉升级（key/ambient/vignette 三层 + 角色三段受光）。评审流程：大脑首轮打回 5 项必修（含点名的技能驱动视觉升级缺执行），工人二轮全部真正修复。验证：后端 worktree 与合并后 main 均 150 passed（含真实 LLM 用例）；前端 tsc/build 零错误。非阻断遗留 6 条挂 todo「批次遗留」。
