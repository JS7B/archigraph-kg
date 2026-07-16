# 个人知识图谱 Archigraph Agent 项目规划

日期：2026-06-16

## 1. 项目定位

这是一个面向个人学习、作品集展示和 AI Coding 实践的完整落地项目。项目会以公开 GitHub 仓库推进，后续开发会结合 git worktree，支持并行探索不同功能分支和实现方案。

项目目标是做出一个可以写进简历、可以本地演示、并且能体现 AI 应用工程能力的知识图谱 Agent：

> 面向个人文档集合，自动完成文档解析、实体识别、关系抽取、Neo4j 知识图谱构建、GraphRAG 检索和可追溯回答生成，并配套一个清晰专业、有像素 Agent 动效的前端工作台。

核心价值不在“聊天机器人”，而在完整展示一条 AI 文档理解链路：

- 解析技术论文、GitHub 仓库文档、产品业务需求文档等资料。
- 从文档中抽取实体、关系和证据片段。
- 将结构化知识落到 Neo4j。
- 结合向量检索、图谱扩展和 GraphRAG 完成问答。
- 展示答案、引用、图谱路径和运行过程。
- 用前端动效表达 Agent 的工作状态，但不牺牲专业工具的清晰度。

## 2. 简历价值点

这个项目应该让面试官看到以下能力：

- LLM 应用工程：OpenAI-compatible 调用、结构化输出、提示词设计、失败重试、成本意识。
- RAG 工程：chunking、embedding、召回、reranking、引用追踪。
- 知识图谱工程：实体建模、关系抽取、Cypher 查询、Neo4j 数据落库。
- GraphRAG：从语义召回到图谱邻域扩展，再组织上下文回答。
- 后端工程：FastAPI、任务执行、状态流、日志、API schema、测试。
- 前端产品能力：文档管理、图谱可视化、运行轨迹、像素 Agent 动画。
- 项目工程化能力：公开仓库、配置隔离、Docker Compose、评估集、README、演示材料。

## 3. 完整能力范围

### 文档输入

正式支持这些输入类型：

- 技术论文：重点支持 PDF。
- GitHub 仓库文档：重点支持 Markdown、README、docs 目录。
- 产品业务需求文档：支持 Markdown、纯文本、PDF，后续按需要接入 docx。

PDF 支持是正式范围。文本型 PDF 必须落地；扫描版 PDF 的 OCR 不作为核心验收，避免项目主线偏成 OCR 工程，但文档解析层需要保留扩展口。

### 知识抽取

系统需要从文档中抽取：

- 实体：人物、机构、项目、技术概念、产品模块、指标、风险点、需求项等。
- 关系：依赖、组成、使用、导致、缓解、属于、对比、影响、约束等。
- 证据：实体和关系必须能追溯到原始 chunk 或文档位置。

实体类型和关系类型不在规划阶段完全定死。开发时围绕样本文档和评估集收敛，避免为了“图谱看起来复杂”而堆无用类型。

### 检索与回答

系统需要完成：

- 问题理解。
- 向量召回。
- 图谱邻域扩展。
- GraphRAG 上下文组织。
- 带引用回答生成。
- 置信提示与证据展示。

接入 GraphRAG 时保留项目级控制权：检索策略、上下文组装、证据追踪、回答结构和前端事件输出都由本项目编排层统一管理。

### 前端体验

前端不是营销页，而是一个实际可用的文档理解工作台：

- 文档库。
- 上传与解析状态。
- 问答区。
- 引用证据区。
- 图谱可视化区。
- 运行事件时间线。
- 像素 Agent 工作区。

前端风格偏清晰、专业、可解释；像素 Agent 是增强记忆点，不喧宾夺主。

## 4. 推荐技术栈

### 后端

- Python 3.11+。
- FastAPI：提供文档、检索、问答、图谱和运行状态 API。
- Pydantic：定义请求、响应和 LLM 结构化输出 schema。
- Uvicorn：本地开发服务。
- 任务执行：优先从简单任务表 / 后台任务开始，必要时引入 Celery、RQ 或 Dramatiq。

### LLM 与 Embedding

- OpenAI-compatible chat completion 接口。
- OpenAI-compatible embedding 接口。
- 所有模型配置通过环境变量管理：
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `CHAT_MODEL`
  - `EMBEDDING_MODEL`

### 图谱与检索

- Neo4j：作为正式图谱存储。
- Docker Compose：本地部署 Neo4j，保证公开仓库可复现。
- Neo4j Python Driver：后端连接 Neo4j。
- Neo4j Vector Index：存储 chunk embedding 并执行向量召回。
- GraphRAG：接入成熟能力，并围绕本项目的文档类型、图谱模型、引用展示和前端状态流做定制。

### 文档解析

- Markdown / txt：直接解析。
- PDF：优先选择 PyMuPDF 或 pypdf，结合实际解析效果决定。
- GitHub 仓库文档：从本地目录读取 README、docs、Markdown 文件和必要的代码注释。
- docx / html：作为工程扩展点预留，不影响主链路设计。

### 前端

- React + Vite + TypeScript。
- Tailwind CSS 或普通 CSS Modules，优先简单稳定。
- 图谱可视化：Cytoscape.js / React Flow / Sigma.js 三选一，选择标准是清晰、稳定、易集成。
- 像素动画：用 CSS sprite 或轻量 canvas 实现状态动画，避免过早引入复杂游戏引擎。

### 工程协作

- 公开 GitHub 仓库。
- 从第一天配置 `.gitignore`、`.env.example` 和安全的密钥管理方式。
- 目录结构保持 git worktree 友好，避免把运行数据、缓存、Neo4j 数据目录和本地样本文档误提交。

## 5. 核心概念模型

本节只定义实现时需要围绕的核心概念，不冻结数据库字段、Pydantic schema 或 Neo4j 属性。具体字段在开发阶段结合 API、前端展示和评估需求逐步收敛。

### Document

表示一份被用户纳入知识库的资料。Document 需要保留来源信息、解析状态、索引状态，并关联切分后的文本片段。

### Chunk

表示文档解析后的文本片段。Chunk 是 RAG 和 GraphRAG 的基础证据单元，需要能回到原始文档位置，支持引用展示和评估。

### Entity

表示从文档中识别出的关键对象。实体需要有名称、类型、描述、来源证据和可合并的规范化线索。

### Relation

表示实体之间的语义关系。关系需要服务检索扩展和解释展示，每条关系都应该尽量带证据来源。

### Mention

表示某个实体在具体 chunk 中出现过。Mention 把抽象实体和原文证据接起来，用于引用、高亮和抽取质量评估。

### Run

表示一次系统执行过程，例如文档导入、索引重建、问答检索或删除文档。Run 用于记录执行轨迹、错误和最终结果。

### RunEvent

表示一次 Run 中发生的阶段性事件。它同时服务后端可观察性和前端动效状态。

### Answer

表示一次问答 Run 的结果。Answer 需要关联答案正文、引用证据、相关实体和图谱路径。

## 6. Neo4j 图谱设计方向

以下是图谱建模方向，不是最终 schema。开发时可以根据 GraphRAG 接入方式、前端图谱展示和评估需求调整。

候选节点：

```cypher
(:Document)
(:Chunk)
(:Entity)
(:Run)
(:Answer)
```

候选关系：

```cypher
(:Document)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONS]->(:Entity)
(:Entity)-[:RELATES {type, confidence, evidence_chunk_id}]->(:Entity)
(:Run)-[:USED_CHUNK]->(:Chunk)
(:Run)-[:USED_ENTITY]->(:Entity)
(:Run)-[:GENERATED]->(:Answer)
(:Answer)-[:CITED]->(:Chunk)
```

业务关系可以先统一落为 `:RELATES`，关系类型作为属性保存。等样本文档和问答评估稳定后，再判断是否拆成更具体的 Neo4j relationship type。

## 7. 核心处理流程

### 文档入库

```text
用户选择文档或仓库目录
-> 后端保存文档元信息
-> 解析文本
-> 切块
-> 生成 embedding
-> 抽取实体和关系
-> 合并实体
-> 写入 Neo4j
-> 创建或更新向量索引
-> 前端展示处理完成状态
```

### GraphRAG 问答

```text
用户输入问题
-> 生成问题 embedding
-> 向量召回相关 chunk
-> 从 chunk 找到关联实体
-> 扩展实体邻域和图谱路径
-> 收集证据 chunk、实体和关系
-> rerank 或过滤证据
-> 组装 GraphRAG 上下文
-> LLM 生成带引用答案
-> 保存 Run、RunEvent 和 Answer
-> 前端展示答案、引用、图谱路径和 Agent 动画
```

### 删除与重建

```text
用户删除文档或请求重建索引
-> 记录 Run
-> 删除或标记相关 Document、Chunk、Mention、Embedding
-> 清理或重算受影响的 Entity / Relation
-> 更新 Neo4j 和向量索引
-> 前端展示碎纸机 / 复印整理等状态动画
```

删除和重建要尽量可追踪，避免图谱里残留孤立节点或过期引用。

## 8. API 边界草案

以下 API 只表达功能边界，不作为最终接口冻结。实现时按“先跑通核心链路，再补齐命名和响应结构”的原则推进。

```text
POST   /api/documents
GET    /api/documents
GET    /api/documents/{document_id}
DELETE /api/documents/{document_id}

POST   /api/documents/{document_id}/reindex
POST   /api/repositories/import

POST   /api/chat
GET    /api/runs/{run_id}
GET    /api/runs/{run_id}/events
GET    /api/runs/{run_id}/events/stream

GET    /api/graph/entities
GET    /api/graph/entities/{entity_id}/neighbors
GET    /api/graph/search?q=...

GET    /api/graph/canonical/communities
GET    /api/graph/canonical/entities/{canonical_id}/subgraph
GET    /api/graph/canonical/search?q=...
```

## 9. 工程化开发路径

### 项目基础设施

目标：让公开仓库具备可运行、可协作、可复现的基础。

工作内容：

- 初始化 Git 仓库结构。
- 创建 backend / frontend / docs / samples / evals 目录。
- 配置 `.gitignore`、`.env.example`、README 草稿。
- 配置 Docker Compose，包含 Neo4j。
- 建立后端和前端的本地启动命令。

验收：

- 新开发者按 README 可以启动 Neo4j、后端和前端。
- 密钥、缓存、运行数据不会被提交。

### 后端基础与配置

目标：建立稳定的 API 服务骨架和配置体系。

工作内容：

- FastAPI 应用结构。
- 配置加载。
- 日志。
- 错误响应。
- 健康检查。
- OpenAI-compatible chat / embedding 客户端。
- Neo4j 连接管理。

验收：

- 健康检查通过。
- 能成功调用 chat 和 embedding。
- 能连接 Neo4j 并执行基础 Cypher。

### 文档解析与切块

目标：把论文、Markdown、GitHub 文档和需求文档转成可检索的 chunk。

工作内容：

- Markdown / txt 解析。
- PDF 解析。
- GitHub 仓库文档导入。
- chunking 策略。
- source metadata 记录。

验收：

- 样本文档能解析成稳定 chunk。
- 每个 chunk 能追溯到来源文档。
- PDF 样本解析结果可用于检索和引用。

### Neo4j 图谱与向量索引

目标：把文档、chunk、实体、关系和 embedding 落到 Neo4j。

工作内容：

- Neo4j 约束和索引。
- Document / Chunk 写入。
- embedding 写入。
- Vector Index 创建与查询。
- Entity / Relation 写入。

验收：

- Neo4j Browser 能看到文档、chunk、实体和关系。
- 向量检索能召回相关 chunk。
- 图谱中没有明显重复或孤立的异常数据。

### 实体识别与关系抽取

目标：从文档中抽取可用于 GraphRAG 的结构化知识。

工作内容：

- LLM 结构化抽取 prompt。
- 实体抽取。
- 关系抽取。
- Mention 证据关联。
- 实体合并与去重。
- 抽取失败重试和错误记录。

验收：

- 样本文档能稳定产生实体和关系。
- 实体和关系能回溯到 chunk。
- 抽取结果可以被前端和 GraphRAG 使用。

### GraphRAG 检索与回答

目标：完成“向量召回 + 图谱扩展 + 证据组织 + 带引用回答”的核心能力。

工作内容：

- 问题 embedding。
- top-k chunk 召回。
- entity neighborhood expansion。
- graph path 收集。
- rerank / filtering。
- GraphRAG context builder。
- answer generation。
- citation and path packaging。

验收：

- 用户问题能得到带引用答案。
- 答案能展示相关实体和关系路径。
- 引用能回到原始 chunk。

### Run 与事件流

目标：让系统执行过程可观察，并为像素 Agent 动画提供事件来源。

工作内容：

- Run 记录。
- RunEvent 记录。
- SSE 或轮询事件接口。
- 文档解析、抽取、检索、生成、删除、重建的事件映射。

验收：

- 前端能看到执行进度。
- 失败时能看到失败步骤和错误摘要。
- 像素 Agent 状态由真实事件驱动。

### 前端工作台

目标：提供清晰专业的完整操作界面。

工作内容：

- 文档库。
- 上传 / 导入入口。
- 问答区。
- 答案和引用区。
- 图谱可视化。
- 运行事件时间线。
- 设置页：模型配置提示、Neo4j 状态、样本导入说明。

验收：

- 用户可以在前端完成导入、索引、提问、查看引用和查看图谱。
- 页面布局不拥挤，重点信息清晰。

### 像素 Agent 动画

目标：为运行状态提供有记忆点但不过度娱乐化的表达。

主要工作流：为Agent设计一个像素小人，根据不同执行任务状态作出不同反应。

状态设计：

```text
idle：待命
uploading：搬运文档
parsing：拆文件
extracting：贴实体标签
linking：拉关系线
indexing：整理档案柜
searching：在文件堆里翻找
checking：拿放大镜校对引用
writing：打字输出答案
deleting：把文件放入碎纸机
rebuilding：复印和重排文件
error：查看错误纸条
```

验收：

- 每个核心操作都有对应动画。
- 动画不遮挡主工作流。
- 动画状态来自 RunEvent。

### 评估与质量保障

目标：让项目不只是 demo，而是能证明效果。

工作内容：

- 准备样本文档集。
- 准备问题与参考答案。
- 标注关键实体和关系。
- 编写 eval 脚本。
- 统计实体召回、关系可用率、引用命中率、明显幻觉率。
- 补充后端单元测试和核心流程集成测试。

验收：

- 有一份可复现的评估报告。
- 核心流程测试通过。
- README 说明如何运行评估。

### 公开展示与简历材料

目标：让项目能被第三方理解、运行和评价。

工作内容：

- 完善 README。
- 绘制架构图。
- 准备演示脚本。
- 录制 GIF 或演示视频。
- 整理简历 bullet。

验收：

- 第三方能按 README 跑起来。
- 演示材料能完整展示文档入库、GraphRAG 问答、引用追踪、图谱可视化和像素 Agent 动效。

## 10. 评估标准

### 文档解析

- 给定样本文档，解析成功率达到 100%。
- 每个 chunk 保留来源文档和位置。
- PDF 样本中的正文能够被正确抽取并参与检索。

### 实体识别

- 手工标注关键实体。
- 实体召回率目标：>= 70%。
- 重要实体需要能回溯到证据 chunk。

### 关系抽取

- 手工标注关键关系。
- 关系可用率目标：>= 60%。
- 关系需要能解释其证据来源。

### GraphRAG 问答

- 准备问题和参考答案。
- 回答必须带引用。
- 引用命中率目标：>= 70%。
- 明显幻觉率目标：<= 20%。

### 前端体验

- 上传、索引、提问、删除、重构索引均有对应状态反馈。
- 图谱视图能展示当前回答涉及的实体和关系。
- 答案区能展开引用 chunk。
- 像素 Agent 动画不影响主要操作效率。

## 11. 推荐简历表述

可在完成后写成：

> 构建个人知识图谱 Archigraph Agent，支持技术论文、GitHub 文档和产品需求文档的解析、实体/关系抽取、Neo4j 图谱落库、向量检索与图谱邻域扩展，并通过 FastAPI + React 实现可追溯问答、引用证据展示、图谱可视化和像素 Agent 运行状态动画。

更工程化版本：

> 基于 FastAPI、Neo4j、OpenAI-compatible API 和 React 实现端到端 GraphRAG 系统，设计 Document/Chunk/Entity/Relation 概念模型，构建向量召回 + 图谱扩展检索链路，并建立问答评估集衡量引用命中率和幻觉率。

## 12. 已确认决策

- 项目需要公开 GitHub，并为后续 AI Coding + git worktree 开发方式做准备。
- 样本文档优先覆盖三类：技术论文、GitHub 仓库文档、产品业务需求文档。
- 前端风格偏清晰、专业，动效作为记忆点，不喧宾夺主。
- Neo4j 使用 Docker 本地部署。
- PDF 解析需要落地，优先保证文本型 PDF 的稳定解析。
- 可以接入 GraphRAG，并围绕本项目的文档类型、图谱模型、引用追踪和前端展示做微调。

## 13. 待确认问题

这些问题进入项目骨架设计时处理：

1. 公开仓库名称和项目英文名。
2. PDF 解析库选择：`pypdf`、`PyMuPDF` 或其他方案。
3. 前端图谱可视化库选择：Cytoscape.js、React Flow 或 Sigma.js。
4. 第一批可公开样本文档来源，避免版权和隐私问题。
5. OpenAI-compatible 服务商和默认模型名。
