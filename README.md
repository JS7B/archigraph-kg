# graphrag-kg-agent

面向个人文档集合（技术论文 / GitHub 仓库文档 / 产品需求文档）的端到端 **GraphRAG** 系统：自动完成文档解析、实体与关系抽取、Neo4j 知识图谱构建、向量召回 + 图谱邻域扩展检索，生成**可追溯引用**的回答，并配套一个清晰专业、带像素 Agent 动效的前端工作台。

> ⚠️ 开发中（WIP）。当前已就绪：项目骨架、Neo4j 本地部署。后端 / 前端尚未实现。

## 技术栈

- **后端**：Python 3.11+ · FastAPI · Pydantic
- **图谱 / 检索**：Neo4j + Vector Index（Docker 本地部署）
- **LLM**：OpenAI-compatible chat & embedding（不绑定具体厂商）
- **文档解析**：PyMuPDF（PDF）· Markdown / txt
- **前端**：React + Vite + TypeScript · Cytoscape.js（图谱可视化）

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

后端、前端启动命令将在对应模块实现后补充。

## 目录结构

```
backend/    后端 FastAPI 应用（WIP）
frontend/   React + Vite + TS 前端（WIP）
docs/       规划与设计文档
samples/    公开样本文档（私有样本放 samples/private/，不提交）
evals/      评估集与脚本（WIP）
```

## 文档

完整规划见 [`docs/personal-kg-graphrag-agent-plan.md`](docs/personal-kg-graphrag-agent-plan.md)：定位、能力范围、概念模型、图谱设计、处理流程、API 边界、评估标准。
