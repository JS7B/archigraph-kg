# 首批质量升级与并行审计设计

## 1. 目标

在不改变 Archigraph 核心产品语义的前提下，完成第一批工程质量升级：

1. 建立可执行的前端 lint 与组件测试门禁，并修复当前 6 个 React Hooks lint 错误。
2. 将 Cytoscape 图谱视图从首屏包中拆出，同时保留视图首次访问后的状态。
3. 修复评估脚本对 Markdown、`Cytoscape.js`、URL 和小数的错误分句，澄清实体召回统计口径。
4. 建立独立于实现工人的 Codex Hook、周期巡检和主窗口终审三层审计。

本批次不修改知识图谱 schema、问答 API、Agentic RAG 策略或前端视觉设计，也不运行会产生模型费用的真实 LLM 评估。

## 2. 工作方式

主仓库 `D:\AgenX\archigraph-kg` 保持在 `main`，只负责规格、评审、合并与任务记录。实现工作分别位于同级物理 worktree：

| 工作线 | 分支 | 物理目录 | 范围 |
| --- | --- | --- | --- |
| 前端质量 | `feat/frontend-quality` | `D:\AgenX\archigraph-kg-frontend-quality` | lint、Vitest、关键状态流测试、图谱拆包 |
| 评估质量 | `feat/evaluation-quality` | `D:\AgenX\archigraph-kg-evaluation-quality` | Markdown 感知分句、指标口径、评估测试 |
| 审计基础设施 | `feat/audit-infrastructure` | `D:\AgenX\archigraph-kg-audit` | repo Hook、分支审计脚本、审计说明 |

每个工人只在自己的固定分支提交，不修改 `main`，不自行合并，不更新 `tasks/todo.md`。主窗口逐分支审计后合并，并在全部合并后统一更新任务清单。

## 3. 前端质量工作线

### 3.1 Lint 与状态流

保留 `eslint-plugin-react-hooks` 的推荐规则，不通过全局关闭 `react-hooks/set-state-in-effect` 规避错误。

- 初始数据加载不再从 effect 同步调用一个会立即 `setState` 的刷新函数；初始加载与用户点击刷新共享无状态的请求函数，各自在异步完成回调中更新状态。
- SSE 终态消费从“观察 events 后在 effect 中同步改状态”调整为订阅回调驱动。`useRunEvents` 暴露稳定的终态通知入口，Workbench 与 Library 在外部事件回调中更新消息、busy 状态和列表。
- 保持现有行为：会话切换不丢历史、Run 结束只清 runId、不清 conversationId、失败事件只落一条错误消息。

### 3.2 测试基础设施

新增最小测试依赖：

- `vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `jsdom`

依赖必须同时进入 `frontend/package.json` 与 `frontend/package-lock.json`。新增 `lint`、`test`、`test:run` 脚本，不引入 Playwright 或其他 E2E 依赖。

首批测试覆盖：

- `useRunEvents` 在 runId 变化时清理旧事件，并且终态回调只消费一次。
- Workbench 成功终态追加一次 Agent 回答、保留 conversationId、刷新会话列表。
- Library 成功/失败终态正确解除 busy，并在成功时刷新文档列表。
- 引用角标插件不污染代码块的既有行为保持通过。

### 3.3 图谱拆包

`GraphView` 改为 `React.lazy` 动态导入。应用初始渲染不请求 Cytoscape chunk；第一次切换到图谱视图后才加载，之后组件保持挂载，来回切换不丢搜索、选中节点和过滤状态。

验收以构建证据为准：生产构建成功，入口 JS chunk 低于 500 KB，Cytoscape 位于独立异步 chunk；即使独立图谱 chunk 仍超过 500 KB，也不得通过提高 Vite 警告阈值隐藏事实。

### 3.4 前端验证

必须通过：

```text
npm run lint
npm run typecheck
npm run test:run
npm run build
```

工作线完成后追加 `frontend/DEVLOG.md`，解释 Vitest、事件回调状态流和动态导入为什么需要。

## 4. 评估质量工作线

### 4.1 分句器

把分句逻辑从 `evals/run_eval.py` 提取为可单测的纯函数。分句器遵循以下边界：

- 中文句号、问号、叹号以及真正的英文句末标点可以结束论断句。
- `Cytoscape.js`、域名、URL、版本号与小数中的点号不能切句。
- Markdown 列表换行可以形成独立论断；空行、围栏标记与纯格式片段不计为论断。
- 引用角标 `[n]` 必须保留在它所支撑的句子中。
- 拒答文本继续按现有规则将幻觉率记为 0。

新增回归测试至少覆盖 `Cytoscape.js`、`React 19.2`、URL、中文句号、Markdown 列表和引用角标。

### 4.2 指标口径

`docs/evaluation.md` 明确区分：

- 标注加权池化实体召回率：当前报告口径 87.7%。
- 逐文档宏平均实体召回率：当前记录 86.6%。

评估报告生成函数同时输出两个命名清晰的字段和表格行，不再用单个“实体召回率”混合表达。历史 `evals/report.md` 是旧快照；没有运行真实 LLM 时不伪造新的实测报告，只在文档中说明快照口径。

### 4.3 评估验证

运行纯单元测试，不触发 LLM 或重写 Neo4j 数据。工作线完成后在 `evals/DEVLOG.md` 记录分句器与半自动幻觉指标的设计取舍。

## 5. 审计基础设施工作线

### 5.1 Repo Hook

新增 `.codex/hooks.json` 与 `.codex/hooks/` 下的确定性审计脚本，监听 `SubagentStop` 和 `Stop`。

- 在 `main` 上不阻断正常会话。
- 在 `feat/*` 分支上检查工作区状态、`git diff --check`、相对 `main` 的改动范围和板块对应验证命令。
- 验证失败时返回 Codex 支持的 `decision: block` JSON，使代理继续修正；`stop_hook_active=true` 时不得再次阻断，避免无限循环。
- Hook 不运行真实 LLM 评估，不打印 `.env`，不自动提交、不合并、不推送。
- Hook 命令同时提供 Windows `commandWindows` 与通用命令入口。

项目级 Hook 需要在受信任仓库中人工审阅后才会运行。本批次当前会话若不能热加载新 Hook，主窗口必须显式调用同一审计脚本，不能把“Hook 文件已存在”当作已执行证据。

### 5.2 10 分钟循环巡检

创建附着在当前任务上的 10 分钟 heartbeat：

- 只读检查 `git worktree list`、三个分支相对 `main` 的 diff、最新提交和失败测试迹象。
- 发现问题时回到当前任务报告；没有新变化时简短记录，不修改文件。
- 不提交、不合并、不推送，不替代主窗口终审。
- 三个分支完成合并或 worktree 被回收后停止。

### 5.3 主窗口终审

每条分支必须经过：

1. 查看 `main...branch` 完整 diff 与提交范围。
2. 运行该板块验证命令。
3. 检查依赖清单、锁文件、DEVLOG 与密钥/运行数据边界。
4. 对发现的问题退回原工人修正；全部通过后才合并。

审计工作线完成后追加 `docs/DEVLOG.md`，解释 Hook 是生命周期机械门禁、heartbeat 是周期观察、主窗口是合并决策者，三者职责不可互换。

## 6. 合并与后续批次

建议先合并审计基础设施，再合并评估质量，最后合并前端质量。每次合并后运行受影响板块测试；三条线全部合并后运行：

```text
conda run -n myself python -m pytest -q
npm run lint
npm run typecheck
npm run test:run
npm run build
```

完整回归中的真实 LLM 测试使用占位环境变量跳过，避免未经单独批准产生费用。

第二批次再引入 `pytest-cov`：先测量当前覆盖率，再建立不低于 70% 的初始门槛；稳定后将 `pytest-cov` 写入 `backend/requirements.txt`。第二批不与本批三个 worktree 并行，避免扩大首轮变更面。

## 7. 完成标准

- 三个物理 worktree 与固定语义分支存在，工人均提交可审计产出。
- 前端 lint、类型、测试、构建全部通过，入口包小于 500 KB。
- 分句器回归测试通过，两个实体召回口径在代码与文档中明确区分。
- Hook 脚本有成功和失败路径测试，周期巡检已创建并能报告工作树状态。
- 主窗口完成逐分支审计、合并、全量回归、`tasks/todo.md` 和相应 DEVLOG 收尾。
- worktree 最终被安全回收，后台巡检停止。
