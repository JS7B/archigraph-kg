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

- [ ] 新开发者按 README 可以启动 Neo4j、后端和前端。（待装 Docker 后端到端验证）
- [x] 密钥、缓存、运行数据不会被提交。（.gitignore 已覆盖，git status 已确认）

### 后端基础与配置

- [ ] 初始化 FastAPI 应用结构。
- [ ] 实现配置加载。
- [ ] 实现日志。
- [ ] 实现统一错误响应。
- [ ] 实现健康检查接口。
- [ ] 实现 OpenAI-compatible chat 客户端。
- [ ] 实现 OpenAI-compatible embedding 客户端。
- [ ] 实现 Neo4j 连接管理。

验证：

- [ ] 健康检查通过。
- [ ] 能成功调用 chat 和 embedding。
- [ ] 能连接 Neo4j 并执行基础 Cypher。

### 文档解析与切块

- [ ] 实现 Markdown 解析。
- [ ] 实现 txt 解析。
- [ ] 实现 PDF 解析。
- [ ] 实现 GitHub 仓库文档导入。
- [ ] 实现 chunking 策略。
- [ ] 记录 source metadata。

验证：

- [ ] 样本文档能解析成稳定 chunk。
- [ ] 每个 chunk 能追溯到来源文档。
- [ ] PDF 样本解析结果可用于检索和引用。

### Neo4j 图谱与向量索引

- [ ] 定义 Neo4j 约束和索引。
- [ ] 写入 Document / Chunk。
- [ ] 写入 embedding。
- [ ] 创建 Neo4j Vector Index。
- [ ] 实现向量查询。
- [ ] 写入 Entity / Relation。

验证：

- [ ] Neo4j Browser 能看到文档、chunk、实体和关系。
- [ ] 向量检索能召回相关 chunk。
- [ ] 图谱中没有明显重复或孤立的异常数据。

### 实体识别与关系抽取

- [ ] 设计 LLM 结构化抽取 prompt。
- [ ] 实现实体抽取。
- [ ] 实现关系抽取。
- [ ] 实现 Mention 证据关联。
- [ ] 实现实体合并与去重。
- [ ] 实现抽取失败重试和错误记录。

验证：

- [ ] 样本文档能稳定产生实体和关系。
- [ ] 实体和关系能回溯到 chunk。
- [ ] 抽取结果可以被前端和 GraphRAG 使用。

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
