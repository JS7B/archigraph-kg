# 评估方法与复现

本文档说明 GraphRAG 系统的评估集构成、指标定义与复现步骤，对应 AGENTS.md 的「验收硬指标」。

## 评估集构成

4 篇样本，全部取自本项目自带文档（零版权风险、可公开）：

| 样本 | 来源 | 类型 | document_id |
|------|------|------|-------------|
| `samples/eval-planning.md` | `docs/personal-kg-graphrag-agent-plan.md` | 技术规划（论文风格） | `eval_eval-planning.md` |
| `samples/eval-agents.md` | `AGENTS.md` | GitHub 项目文档 | `eval_eval-agents.md` |
| `samples/eval-api-needs.md` | `docs/frontend-backend-interface-needs.md` | API 契约文档 | `eval_eval-api-needs.md` |
| `samples/eval-parsing-design.md` | `docs/superpowers/specs/...parsing-chunking-design.md` | 设计规格 | `eval_eval-parsing-design.md` |

人工标注（ground truth）在 `evals/ground_truth.jsonl`，每行一篇样本的关键实体、关系、问答问题。

## 指标定义

### ① 解析成功率
- **分母**：样本总数（4）
- **分子**：成功解析（不抛异常）且产出非空 chunk 的样本数
- **完整性校验**：每个 chunk 满足 `raw_text[char_start:char_end] == chunk.text`（偏移可追溯，对应"引用必须能落到原始 chunk"硬要求）

### ② 实体召回率（两种汇总口径）
- **单篇分母**：该文档人工标注的关键实体数（按 normalized_name，即 `name.lower().strip()` 去重）
- **单篇分子**：系统抽出的实体归一名集合 ∩ 标注归一名集合的大小
- **匹配规则**：大小写不敏感的名称匹配（对齐抽取层 `merge_extractions` 的合并键 `(normalized_name, type)`）
- **标注加权池化实体召回率（pooled）**：先汇总各文档命中数与标注数，再用 `总命中数 / 总标注数` 计算；标注实体较多的文档权重更高，**≥ 70% 的验收阈值使用此口径**
- **逐文档宏平均实体召回率（macro）**：先计算每篇文档召回率，再对各篇等权平均；用于观察不同文档是否表现均衡，不承担当前硬阈值
- **失败与零标注策略**：解析失败的文档仍以 `0 / 该文档唯一标注数` 进入 pooled 和 macro，不能因失败而退出分母；zero-gold 文档不增加 pooled 的分子或分母，但其 macro 值按 `0.0` 计。若评估集为空或全部 zero-gold，pooled 返回 `0.0`

`evals/report.md` 是 **2026-07-03 的历史快照**，其中旧的单一“实体召回率”标签表示 pooled 口径，实测为 **87.7%**。同一快照四篇明细的 macro 平均为 **86.6%**。评估脚本现在会同时输出 `entity_recall_pooled` 与 `entity_recall_macro`，避免混用两种统计含义；本次质量修复未调用真实模型，因此没有改写历史快照。

抽出但未命中 `ground_truth.jsonl` 的实体只进入**待复核清单**。这里的 ground truth 标的是关键实体，不是穷举全集，所以“未匹配”不等于“错误”，不能直接进入 precision 的错误分子或分母。

### ③ 关系可用率
- **分母**：LLM 原始抽出的关系总数（合并前）
- **分子**：合并后成链的关系数（两端实体都成功解析的）
- **含义**：合并阶段会丢弃"端点解析不到实体"的关系，丢弃的算不可用

关系可用率只证明关系在合并后能够成链，**不证明关系类型、方向和语义正确**。关系语义质量使用下方人工复核夹具中的 semantic precision 单独衡量。

### ④ 引用命中率
- **分母**：问答问题总数
- **分子**：答案正确（正文含标注答案关键词）且有引用的问数
- **含义**：系统是否既回答正确又给出可追溯引用。答案准确率（正文含标注答案关键词的比例）单独统计，引用命中率要求"准确 且 有引用"
- **设计修正**：早期算法要求 chunk snippet 逐字含特征词，过严——语义召回的 chunk 未必逐字含标注词，但答案正确且有引用即应算命中

### ⑤ 明显幻觉率（半自动）
- **分母**：答案正文按句切分后的总句数
- **分子**：无角标引用 `[n]` 的句子数
- **方法**：Markdown 感知分句器忽略围栏代码，按列表换行和真正的中英文句末标点切分，同时保留 `Cytoscape.js`、版本号、小数、域名与 URL 内部的点号和引用角标；机器再把所有“无引用论断”写入 `evals/report.md` 的「待人工复核」清单，由人判断是否确为无依据内容
- **已知局限**：纯自动判幻觉是开放问题，半自动（机器列疑点 + 人复核）诚实可复现；纯拒答（"根据现有资料无法回答"）不计入幻觉

### ⑥ 人工复核图谱质量基线

`evals/quality_fixtures.jsonl` 是一组不调用 LLM、Neo4j 的确定性人工复核夹具。每个 accepted 候选都显式记录是否命中关键实体标注、人工正确性标签（可为 `null`，表示尚未复核）和 provenance 是否存在；每个夹具还声明 accepted 候选总体数量和抽样方法。`evals/quality_report.md` 必须连同复核覆盖率一起阅读。

- **实体 precision**：分母是 accepted 且已有人工 `正确/错误` 标签的实体数；分子是其中人工判断正确的实体数。`reviewed_correct=null` 的未匹配项保留为 review candidate，不进入分母。
- **关系 semantic precision**：分母是 accepted 且已人工判断的关系数；分子是其中方向、类型和语义都正确的关系数。它与“关系可用率”不是同一个指标。
- **provenance completeness**：分母是夹具中全部 accepted 实体与关系；分子是其中具有可定位证据的数量。未 accepted 的过滤项不进入该分母。
- **人工复核覆盖率**：分母是夹具声明的 accepted 候选总体，分子是已经获得人工正确性标签的候选。precision 只能代表这部分已复核样本，不能外推成生产全图质量。
- **空输入口径**：分母为零时返回 `n/a (0/0)`，不把“没有样本”伪装成 100%。

当前夹具故意同时包含人工正例、人工负例和未复核候选，从而让 precision 具有非零分母，同时证明未匹配项不会自动被算错。它只是用于冻结指标语义的小型夹具基线，**不能替代真实模型运行或生产图谱快照**。

### ⑦ Accepted 图结构诊断

结构诊断只使用夹具中的 accepted 实体和关系，以无向邻接观察图的展示风险；它不修改生产入库逻辑：

- **孤立实体**：accepted 图中度为 0 的实体。
- **度为 1 的实体**：只有一个唯一邻居的实体。
- **低置信关系**：`confidence < 0.6` 的 accepted 关系；阈值在纯函数调用中显式传入。
- **跨文档 normalized-name 重复**：按现有 `name.lower().strip()` 口径归一后，出现在两个及以上夹具文档中的名称。
- **组件规模分布**：accepted 图每个无向连通组件的节点数及相同规模的组件数量。
- **疑似泛化 hub**：名称命中显式泛化词表且唯一邻居数至少为 3 的实体。它只是审查信号，不会自动删除节点。

## 复现步骤

### 纯夹具质量基线（无需外部服务）

在仓库根目录运行：

```bash
python -m evals.quality_baseline
```

命令会验证 JSONL 字段和关系端点，计算人工复核指标与结构诊断，并确定性覆盖写入 `evals/quality_report.md`；不会读取 `.env`、调用模型或连接 Neo4j。测试使用 `python -m pytest evals/tests -q`。

### 真实模型历史评估

#### 前置
1. Neo4j 容器在跑：`docker start graphrag-neo4j`
2. `.env` 配好（`OPENAI_BASE_URL`/`OPENAI_API_KEY`/`CHAT_MODEL`/`EMBEDDING_MODEL`/`EMBEDDING_DIM`/Neo4j 连接）
3. 在 `myself` conda 环境

#### 运行
```bash
cd backend
python ../evals/run_eval.py
```

脚本会：
1. 解析 4 篇样本 → 入库（document_id 用 `eval_` 前缀）
2. 抽取实体关系 + 算 pooled/macro 两种实体召回率与关系可用率
3. 跑每个问题 → 算引用命中率 + 列幻觉疑点
4. 输出 `evals/report.md`（含四项指标实测值 + 逐篇明细 + 待复核清单）
5. **自动清理** `eval_` 前缀数据（不污染共享 Neo4j）

## 已知局限
- **样本量小**（4 篇）：够证明指标可算、可复现，不求统计显著
- **人工复核夹具更小**（2 个手工切片）：只用于冻结 precision、provenance 和结构诊断口径，不代表当前模型或生产图谱水平
- **幻觉率半自动**：需人工复核，非全自动
- **实体召回用名称匹配**：未做语义近义合并（如"Neo4j 数据库"与"Neo4j"算不同实体），可能低估召回率

## 目标值（AGENTS.md 验收硬指标）
- 解析成功率 **100%**
- 标注加权池化实体召回率（pooled） **≥ 70%**
- 逐文档宏平均实体召回率（macro）作为参考指标
- 关系可用率 **≥ 60%**
- 引用命中率 **≥ 70%**
- 明显幻觉率 **≤ 20%**
