# Knowledge Graph Quality Reconstruction Roadmap

> **For agentic workers:** Each worktree must follow its own detailed plan, use TDD, commit only on its fixed branch, and report evidence to the main window.

**Goal:** 保留 Archigraph 自研管线，按六条固定 worktree 逐层降低图谱噪声、提高实体/关系可信度，并将前端改造成局部、可回溯的图谱探索器。

**Architecture:** 先建立评估基线，再给解析块增加内容类型，再在候选层实施严格 Schema/证据校验，随后做跨文档实体解析和关系治理，最后提供社区/子图 API 与稳定前端视图。每一层只消费上游明确的数据接口，不把第三方框架引入为黑盒主链路。

**Tech Stack:** Python 3.11+ / Pydantic / FastAPI / Neo4j / OpenAI-compatible LLM / React + Vite + TypeScript / Cytoscape.js / pytest / Vitest。

## Global Constraints

- 主仓库 `D:\AgenX\archigraph-kg` 只负责规格、评审、合并和任务记录。
- Worktree 位于主仓库同级目录；固定分支名使用 `feat/kg-*`，工人不修改 main、不合并、不推送。
- 任何实现先写失败测试，再写最小代码；每个任务完成后运行本任务的窄测试和板块回归。
- 不移除现有 provenance、引用追踪、RunEvent、Neo4j 存储或项目级 GraphRAG 编排。
- 代码块、配置块和日志块默认不进入普通实体抽取；专用抽取必须显式声明策略。
- 每个 accepted 实体/关系必须能定位到原始 Chunk；review/rejected 不得伪装成 accepted。
- 新依赖先记录用途并确认，随后同步更新对应 requirements 或前端 lockfile。
- 每条工作线更新所属 DEVLOG，并在提交前运行 `git diff --check` 与 `git status --short`。

## Worktree sequence

| Order | Branch | Worktree | Deliverable | Base |
| --- | --- | --- | --- | --- |
| 1 | `feat/kg-evaluation` | `D:\AgenX\archigraph-kg-evaluation` | 精确率/噪声/关系正确率基线与标注夹具 | main |
| 2 | `feat/kg-parsing` | `D:\AgenX\archigraph-kg-parsing` | 内容类型识别与 provenance 元数据 | merged evaluation |
| 3 | `feat/kg-extraction` | `D:\AgenX\archigraph-kg-extraction` | 严格 Schema、证据和候选裁剪 | merged parsing |
| 4 | `feat/kg-resolution` | `D:\AgenX\archigraph-kg-resolution` | 跨文档实体消歧与关系治理 | merged extraction |
| 5 | `feat/kg-community-api` | `D:\AgenX\archigraph-kg-community-api` | 社区/重要性/子图过滤 API | merged resolution |
| 6 | `feat/graph-experience` | `D:\AgenX\archigraph-kg-graph-experience` | 稳定布局、邻域展开、证据面板 | merged community-api |

## Integration gates

1. Main reviews the complete diff and tests for a worktree before merge.
2. The next worktree is created from the newly merged main, never from a stale branch.
3. After the final merge run backend full tests, evaluation tests, frontend lint/typecheck/test/build, and the project audit hook.
4. Only after final verification remove all temporary worktrees and merged local branches.

## Deferred plan creation

Detailed plans for parsing, extraction, resolution, community API, and frontend are created immediately before their corresponding worktree, after the previous contract is merged. This prevents speculative file interfaces from drifting while preserving the fixed sequence above.

