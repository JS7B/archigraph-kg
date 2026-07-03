# 交接清单（后端工人 · feat/backend）：抽取质量升级 + 图谱 API 排序 + 评估扩容

> 大脑 2026-07-03 签发。开工前先把最新 main 合进 feat/backend（本批依赖 main 上
> `6d0d778`（逐 chunk 进度）与 `d3e0eef`（前端合并），确保基线一致）。
> 完成后本地 commit，口头通知大脑评审合并。**不碰 main、不自行合并。**

## 背景

用户反馈图谱实体「机械粗糙」：无意义实体入图；评估显示实体召回 57.1%（8/14，单篇基线）
未达 70% 硬指标。排查结论：根因约 60% 在抽取 prompt，归并/过滤/评估各有欠账。
展示层降噪由前端工人并行处理（handoff-frontend-answer-graph-agentroom.md），
后端负责把「源头产出」和「排序数据」做对。

## 已定决策（大脑头脑风暴收敛，不再讨论）

- **不引入抽取框架**（MS GraphRAG / LlamaIndex / LangChain graph transformer /
  neo4j-graphrag-python 均评估过）：违反决策边界「GraphRAG 接入但保留项目级控制权」；
  根因在 prompt 而非框架（框架内部同样是 prompt+merge，换了还得调）；自研抽取链路
  是本项目简历叙事的核心。
- **写入层不做硬过滤**：曾考虑「单次提及且无关系的实体不入图」，否决——会直接拖低
  召回率（ground_truth 里有的实体就出现一次）。改为写入 `mentionCount` 数据，
  降噪交给展示层排序/过滤。
- 实体类型收敛为**封闭集合**，禁止模型自拟类型。

## 任务清单

### B1 抽取 prompt 重写（`app/extraction/prompt.py`）— 主攻

1. 实体类型改封闭集合（沿用现有八类：人物/机构/项目/技术/概念/产品模块/指标/需求项/
   风险点，可微调命名但必须封闭），明确「不属于任何类型则不抽取」，删除「可自拟」。
2. 加排除清单：不抽代词、章节标题、泛化名词（如「系统」「项目」「功能」「用户」）、
   动词短语、完整句子式描述。
3. 加枚举展开指令：技术栈/依赖/工具列举中**每个具名技术、库、框架、语言单独成实体**
   （评估漏抽的 React/Vite/TypeScript/Python/Vector Index/OpenAI 全部来自
   `samples/eval-agents.md` 的一句技术栈列举）。
4. 加 1-2 个中英混合 few-shot 正例，包含「该抽 vs 不该抽」对比；明确英文术语保留
   原始拼写与大小写（如 `Neo4j` 不写成 `neo4j`）。
5. 保持现有 JSON 输出结构不变（下游 `ChunkExtractionResult` 不动）。

→ 验证：先跑 `tests/extraction` 全过；再做 B5 评估看指标。

### B2 归并 key 去 type（`app/extraction/merge.py`）

- 归并 key 从 `(normalized_name, type)` 改为 `normalized_name`；type 冲突取出现次数
  最多者（并列取先见）。消除「React(技术) 与 React(概念) 碎成两节点」。
- `mention_chunk_ids` 语义不变；`_resolve` 关系端点解析同步适配。
- 别名/变体归并（React 19→React 之类）**本轮不做**——规则化风险高（版本号有时就是
  独立实体），先看 B1 收敛后的实际碎片情况再议。

→ 验证：`tests/extraction/test_merge.py` 更新并通过（同名异型合并、type 多数决）。

### B3 Entity 写入 mentionCount（`app/extraction/writer.py`）

- 写 Entity 时 SET `mention_count = len(mention_chunk_ids)`（本文档内计数，Entity
  本就带 document_id 按文档隔离）。不做任何过滤。

→ 验证：writer 测试补断言。

### B4 图谱实体列表按重要性排序（`app/routers/graph.py`）

- `_LIST_ENTITIES` 从 `ORDER BY e.name` 改为按度数降序（度数 = MENTIONS 入边 +
  RELATES 出入边，Cypher `COUNT {}` 或 `size()` 实现），次序键用 name 保证稳定。
- 响应每个实体增加 `degree` 与 `mentionCount`（camelCase），供前端分级展示。
  这是前端 F2 的数据依赖，**优先做**（前端有 edges 兜底计算，不阻塞但尽早）。

→ 验证：`tests/routers/test_graph.py` 补排序与字段断言。

### B5 评估扩容（`evals/run_eval.py` + 重跑）

1. 从单篇基线扩到全量 4 篇样本，报告按篇列明细 + 汇总均值。
2. 报告增加「抽出实体总数 / 标注数」与**未匹配抽出实体清单**（让「噪声」在报告里
   可见，弥补只量召回的盲区）；召回算法本身不改（保持与 57.1% 基线可比）。
3. 改完 B1-B3 后：清库重新入库 4 篇样本 → 跑评估 → 更新 `evals/report.md`。

→ 验收：实体召回 ≥ 70%。若一轮未达标，允许基于报告再迭代一次 prompt；仍未达标则
如实记录并列出漏抽清单交大脑。

### B6 问答输出格式指示（`app/qa/prompt.py`）— 顺手小改

- 系统提示补一句输出格式约定：用 Markdown 组织回答（短段落、要点用列表），
  引用角标 `[n]` 紧跟被支撑的句子。**不得影响** `_generate_final_answer` 的
  `\[(\d+)\]` 角标净化逻辑。配合前端本轮的 Markdown 渲染改造。

→ 验证：`tests/qa` 全过。

## 硬约束

- 密钥零提交；模型配置只走环境变量。
- 引用可追溯红线不动：MENTIONS / RELATES 的 evidence 链路不得削弱。
- Stage 枚举与 RunEvent 契约不动（前端锁定）。
- 共享 Neo4j 错峰：清库重建评估数据前，确认前端工人没在跑依赖图数据的联调。

## 交付定义

`tests/` 全量通过（真实 LLM 用例无 key 正确 skip）+ `evals/report.md` 更新 +
`backend/DEVLOG.md` 按模板补一条（重点写清 prompt 改了什么、为什么、指标前后对比）+
本地 commit 通知大脑。
