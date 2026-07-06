# graphrag-kg-agent · Archigraph（档图）

面向个人文档集合（技术论文 / GitHub 仓库文档 / 产品需求文档）的端到端 **Agentic GraphRAG** 系统：自动完成文档解析、实体与关系抽取、Neo4j 知识图谱构建，再由一个 **ReAct 检索-反思 Agent**（LLM 自主决定检索什么、证据够不够、要不要换查询再查）生成**可追溯引用**的回答，**多轮对话记忆**让 Agent 记住同一会话的上下文（历史存图谱、可恢复），并配套一个清晰专业、带像素 Agent 房间动效的前端工作台。

> 展示名 **Archigraph** = archive（档案）+ graph（图谱），呼应招牌组件「像素档案员 AgentRoom」。
> 状态：核心链路全部完成且端到端验证通过（解析 → 图谱 → 抽取 → Agentic RAG 问答 → 多轮对话记忆 → Run/SSE → 前端工作台 → 评估），并经一轮 PR 审计整改（安全/可复现/正确性/无障碍加固）。

## 技术栈

- **后端**：Python 3.11+ · FastAPI · Pydantic
- **图谱 / 检索**：Neo4j + Vector Index（Docker 本地部署）
- **LLM**：OpenAI-compatible chat & embedding（不绑定具体厂商）
- **Agent**：自研 ReAct 循环 + OpenAI 原生 function calling（不引 LangGraph/LangChain）
- **文档解析**：PyMuPDF（PDF）· Markdown / txt
- **前端**：React 19 + Vite + TypeScript · Cytoscape.js（图谱可视化）

## 环境要求

- Python 3.11+
- Node.js 18+
- Docker Desktop（用于本地 Neo4j）

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM 配置与 Neo4j 密码

# 2. 启动 Neo4j
docker compose up -d neo4j

# 3. 验证：浏览器打开 http://localhost:7474
#    用 neo4j / <你在 .env 设的 NEO4J_PASSWORD> 登录
```

后端、前端启动详见 [`运行说明.md`](运行说明.md)。

### 后端 API（已就绪）

```bash
conda activate myself     # 激活 Python 环境（如用 conda）
cd backend
python -m uvicorn app.main:app --reload --port 8000
# API: http://localhost:8000，交互文档 /docs，健康检查 /health、/health/deps
```

核心端点：文档上传入库 `POST /api/documents`、问答 `POST /api/chat`（异步 Agentic RAG + SSE 进度流 `/api/runs/{runId}/events/stream`，多轮检索时前端像素房间跟着 Agent 决策实时走）、图谱查询 `GET /api/graph/entities`、**会话管理** `GET/POST /api/conversations`（多轮对话记忆：历史存 Neo4j、问答向量化、刷新可恢复）。

> 安全：若在 `.env` 配置了 `API_KEY`，所有非 `/health` 接口需在请求头带 `X-API-Key`；为空（默认）则不鉴权，便于本地开发。

## 评估

系统有一套可复现的评估，量化解析成功率、实体召回率、关系可用率、引用命中率、幻觉率五项指标。详见 [`docs/evaluation.md`](docs/evaluation.md)。

```bash
# 前置：Neo4j 容器在跑 + .env 配好 LLM
cd backend
python ../evals/run_eval.py
# 产出 evals/report.md（指标实测值 + 逐篇明细 + 待复核清单）
```

## 目录结构

```
backend/    后端 FastAPI 应用（Agentic RAG / 图谱 / 抽取 / Run·SSE / 多轮对话记忆）
frontend/   React + Vite + TS 前端工作台（三视图 + 会话侧边栏 + 像素 Agent 房间）
docs/       规划与设计文档
samples/    公开样本文档（私有样本放 samples/private/，不提交）
evals/      评估集与脚本（ground_truth + run_eval.py）
```

## 文档

- [`项目说明.md`](项目说明.md)：项目总说明（架构、图谱模型、入库/问答链路、对话记忆、事件流、评估、设计取舍）
- [`运行说明.md`](运行说明.md)：本地启动完整步骤 + 常见问题
- [`docs/personal-kg-graphrag-agent-plan.md`](docs/personal-kg-graphrag-agent-plan.md)：总规划（定位、概念模型、图谱设计、流程、API、评估）
- [`backend/后端说明.md`](backend/后端说明.md) · [`frontend/前端说明.md`](frontend/前端说明.md)：前后端工程实现详解
