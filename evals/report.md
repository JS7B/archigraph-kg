# 评估报告

生成时间：2026-07-03 18:06

## 汇总指标

| 指标 | 实测 | 目标 |
|---|---|---|
| 解析成功率 | 100.0% | 100% |
| 实体召回率 | 87.7% | ≥70% |
| 关系可用率 | 100.0% | ≥60% |
| 引用命中率 | 89.6% | ≥70% |
| 明显幻觉率 | 26.5% | ≤20% |

## 逐篇明细

### eval-agents.md (GitHub 项目文档)
- 解析: 13 chunks, 偏移完整性=OK
- 抽取: 69 实体 / 30 关系 / 0 失败chunk
- 实体召回率: 78.6%
- 抽出实体总数: 69 / 标注数: 14
  - 漏掉的标注实体: Python, DEVLOG, OpenAI
  - 未匹配抽出实体（噪声候选，共 58 个）: 个人知识图谱, Agent, GraphRAG系统, 前端工作台, Python 3.11+, Docker, OpenAI-compatible chat, OpenAI-compatible embedding, docs/personal-kg-graphrag-agent-plan.md, tasks/todo.md, tasks/lessons.md, README.md, .env.example, docker-compose.yml, docs/DEVLOG.md, 基础设施, 全局工作流, 入库, 问答, 删除重建
- 关系可用率: 100.0%
- Q: 项目用什么图谱数据库？
  - 引用命中率: 100%, 幻觉率: 50%, 置信度: high
  - 答案: 根据文档片段，项目使用的图谱数据库是 **Neo4j**。系统通过 Neo4j 进行知识图谱的存储与向量索引 [1][2]。...
- Q: 前端技术栈包含哪些？
  - 引用命中率: 100%, 幻觉率: 75%, 置信度: medium
  - 答案: 前端技术栈包含以下组件 [1]：

- **React**（UI 框架）
- **Vite**（构建工具）
- **TypeScript**（语言）...
- Q: 像素 Agent 动画的状态由什么驱动？
  - 引用命中率: 100%, 幻觉率: 0%, 置信度: medium
  - 答案: 像素 Agent 动画状态必须来自真实的 `RunEvent`，不得用前端伪造状态驱动 [1]。...

### eval-planning.md (技术规划)
- 解析: 52 chunks, 偏移完整性=OK
- 抽取: 195 实体 / 120 关系 / 0 失败chunk
- 实体召回率: 100.0%
- 抽出实体总数: 195 / 标注数: 18
  - 未匹配抽出实体（噪声候选，共 177 个）: 个人知识图谱, 知识图谱Agent, 向量检索, 图谱扩展, 文档解析, 实体识别, 关系抽取, git worktree, 像素Agent动效, 前端工作台, AI, AI Coding, GitHub, OpenAI, 结构化输出, 提示词设计, 失败重试, 成本意识, chunking, 召回
- 关系可用率: 100.0%
- Q: 项目的核心概念模型包含哪些实体？
  - 引用命中率: 75%, 幻觉率: 20%, 置信度: high
  - 答案: 根据现有文档片段，项目的核心概念模型包含以下实体：

- **文档（Document）** [4]  
- **实体（Entity）** [1][4]  
- **关系（Relation）** [1]...
- Q: 图谱可视化候选了哪些库？
  - 引用命中率: 100%, 幻觉率: 71%, 置信度: high
  - 答案: 根据文档，图谱可视化候选了以下三个库 [1][2]：

- **Cytoscape.js**
- **React Flow**
- **Sigma.js**

选择标准是清晰、稳定、易集成 [2]。...
- Q: PDF 解析考虑用哪些库？
  - 引用命中率: 100%, 幻觉率: 25%, 置信度: high
  - 答案: PDF 解析考虑了以下库：

- `pypdf` 和 `PyMuPDF` 是主要候选方案 [1]。
- 优先选择 `PyMuPDF` 或 `pypdf`，最终结合实际解析效果决定 [3]。
- 此外，...

### eval-api-needs.md (API 契约文档)
- 解析: 13 chunks, 偏移完整性=OK
- 抽取: 72 实体 / 47 关系 / 0 失败chunk
- 实体召回率: 83.3%
- 抽出实体总数: 72 / 标注数: 12
  - 漏掉的标注实体: multipart, FastAPI
  - 未匹配抽出实体（噪声候选，共 62 个）: 前端工作台脚手架, snake_case, JSON, 错误响应结构, apiFetch, VITE_API_BASE_URL, http://localhost:8000, TS, 先跑通再命名, /health, /health/deps, Neo4j, LLM, 文档库视图, 问答工作台, 像素Agent动画, 图谱探索视图, GraphRAG, Run, pdf
- 关系可用率: 100.0%
- Q: 问答响应的 JSON 字段用什么命名风格？
  - 引用命中率: 100%, 幻觉率: 0%, 置信度: medium
  - 答案: 问答响应的 JSON 字段统一使用 **camelCase** 命名风格 [1]。这是前端工作台脚手架的统一约定，后端若内部使用 snake_case，需在序列化层进行转换 [1]。...
- Q: 图谱关系类型先统一用什么？
  - 引用命中率: 100%, 幻觉率: 0%, 置信度: high
  - 答案: 根据文档，图谱业务关系先统一使用关系类型 `:RELATES`，具体的业务类型（如依赖、组成、使用等）作为属性 `relationType` 保存 [1][2]。这个设计便于在样本文档和问答评估稳定后...
- Q: 前端用什么库渲染图谱？
  - 引用命中率: 100%, 幻觉率: 60%, 置信度: high
  - 答案: 前端使用 **Cytoscape.js** 渲染图谱 [2]。  
在技术选型中，也提到了 **React Flow** 和 **Sigma.js** 作为备选，但当前项目明确采用 Cytoscape...

### eval-parsing-design.md (设计规格)
- 解析: 24 chunks, 偏移完整性=OK
- 抽取: 79 实体 / 53 关系 / 0 失败chunk
- 实体召回率: 84.6%
- 抽出实体总数: 79 / 标注数: 13
  - 漏掉的标注实体: MarkdownParser, PDFParser
  - 未匹配抽出实体（噪声候选，共 68 个）: Neo4j, embedding, HTTP, Markdown, PDF, GitHub, 纯文本, 结构感知切分, provenance粒度, 字符偏移, PDF页码, Markdown标题路径, Pydantic, markdown_parser, text_parser, pdf_parser, repo_importer, base, models, parser
- 关系可用率: 100.0%
- Q: 解析器产出的最终文本片段叫什么？
  - 引用命中率: 100%, 幻觉率: 0%, 置信度: high
  - 答案: 解析器（parser）产出的中间产物是 `ParsedDocument`，但**最终的文本片段是 `Chunk`**[1][3]。  
- `ParsedDocument` 包含原始文本和语义块（`B...
- Q: PDF 解析依赖什么库？
  - 引用命中率: 100%, 幻觉率: 0%, 置信度: high
  - 答案: PDF 解析依赖 **PyMuPDF** 或 **pypdf** 这两个库 [1][2]。实际解析时会根据效果优先选用其中之一 [2]，其中 PyMuPDF 已在 `requirements.txt`...
- Q: Chunk 的来源位置包含哪些字段？
  - 引用命中率: 0%, 幻觉率: 17%, 置信度: high
  - 答案: 根据文档，Chunk 的来源位置（provenance）包含以下字段：

- `document_id`：追溯 Chunk 所属的原始文档 [1][2]。
- 字符偏移 `[start, end)`：...

## 待人工复核的无引用论断

> 以下句子在答案中无角标引用，可能含幻觉。需人工判断是否确为无依据内容。

1. 根据文档片段，项目使用的图谱数据库是 **Neo4j**
2. - **React**（UI 框架）
3. - **Vite**（构建工具）
4. - **TypeScript**（语言）
5. 根据现有文档片段，项目的核心概念模型包含以下实体：
6. - **Cytoscape
7. js**
8. - **React Flow**
9. - **Sigma
10. js**
11. PDF 解析考虑了以下库：
12. 前端使用 **Cytoscape
13. 在技术选型中，也提到了 **React Flow** 和 **Sigma
14. js** 作为备选，但当前项目明确采用 Cytoscape
15. 根据文档，Chunk 的来源位置（provenance）包含以下字段：
