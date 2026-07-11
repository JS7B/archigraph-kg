# 知识图谱质量重构与图谱体验升级设计

## 1. 背景与目标

当前构图链路是“逐 Chunk 调用 LLM → 宽松 JSON 校验 → 文档内名称归一 → 直接写入 Neo4j”。
主要问题是：代码/配置内容没有和自然语言分流，实体类型与关系模式没有强校验，实体归一只支持小写加空白裁剪，关系置信度没有用于裁剪，评估主要看召回与端点可解析率，前端则默认把全图用随机力导向一次性摊开。

本次重构目标：

1. 降低代码、日志、路径、泛化名词和错误关系造成的图谱噪声。
2. 让每个入图实体和关系都具备可定位来源、证据和质量状态。
3. 提供跨文档实体归一、别名管理和可解释的合并依据。
4. 将评估从“召回优先”升级为召回、精确率、关系语义正确率和噪声率并重。
5. 将前端从“全图静态展示”升级为稳定、渐进、可回溯的子图探索。

不整体替换现有 FastAPI、Neo4j、RunEvent、引用追踪和项目级 GraphRAG 编排；只借鉴成熟开源框架的模块边界和质量控制策略。

## 2. 设计原则

- Schema-first：先定义实体、关系和合法连接模式，再让模型抽取。
- Evidence-first：没有原文证据的候选不得直接进入 accepted 图谱。
- Code-aware：代码、配置、日志和正文使用不同处理策略，普通实体抽取默认跳过代码块。
- Candidate-first：LLM 输出先作为候选，不直接等同于事实。
- Conservative resolution：实体合并宁可保留候选和别名，也不做不可解释的强合并。
- Provenance preserved：所有合并、裁剪和关系判断都保留来源 Chunk 与处理原因。
- Local-first visualization：默认展示可解释的小范围子图，通过交互逐层展开。
- Project ownership：第三方框架只提供可借鉴的模式，业务 Schema、证据链、API 和前端事件仍由本项目控制。

## 3. 目标数据模型

### 3.1 解析层

在现有 `Block`/`Chunk` 基础上增加内容语义元数据：

- `content_kind`: `prose`、`code`、`config`、`table`、`list`、`log`、`heading`。
- `language`: 可选的代码语言或文档语言。
- `heading_path`、`char_start`、`char_end`：继续保持可追溯。
- `extraction_policy`: `normal`、`skip`、`specialized`。

代码块、配置块和日志块默认不进入普通实体抽取；若需要抽取 API、模块或类名，必须走显式的 specialized 策略。

### 3.2 抽取层

新增候选形态，不直接复用最终图谱形态：

- `ExtractionCandidate`：候选实体或关系、来源 Chunk、原始文本证据、模型置信度、Schema 校验结果。
- `CandidateDecision`：`accepted`、`review`、`rejected`，附带确定性原因。
- 关系必须包含 `source`、`target`、`type`、`confidence`、`evidence`；`evidence` 必须能在源 Chunk 中定位。

实体类型与关系类型使用 Pydantic 枚举或等价的严格校验；实体类型与关系类型之间增加 pattern 矩阵，禁止任意端点组合。

### 3.3 规范实体层

规范实体至少包含：

- `canonical_name`、`normalized_name`、`entity_type`；
- `aliases`、`language_variants`；
- `source_document_ids`、`mention_chunk_ids`；
- `resolution_method`、`resolution_confidence`、`resolution_evidence`。

跨文档合并采用“精确归一 → 别名/缩写 → 模糊候选 → 语义候选 → 仅对冲突项进行 LLM 判定”的顺序。任何自动合并都必须可解释和可回滚。

## 4. 构图流水线

```text
文档加载
  → AST/布局解析与内容分类
  → provenance 保留的语义切块
  → 候选实体/关系抽取
  → Structured Output + Schema 校验
  → 证据定位与确定性裁剪
  → 跨 Chunk / 跨文档实体解析
  → 关系方向、类型、置信度校验
  → accepted/review 分层写入 Neo4j
  → 社区/重要性计算
  → 前端局部子图探索
```

### 4.1 解析与切块

Markdown 使用 AST 或等价的结构解析；至少识别代码围栏、表格、列表、标题和正文。PDF 保持现有文本型 PDF 主线，同时保留页面和字符偏移。Chunk 不能跨越不兼容的内容类型或标题边界。

### 4.2 抽取与校验

抽取提示只负责提出候选；确定性层负责：

- 严格实体/关系枚举；
- 关系端点必须来自同一候选集合；
- 证据必须是 Chunk 中的可定位片段；
- 泛化名词、代词、章节标题、纯路径和代码标识符按策略过滤；
- 低置信度、冲突或违反 pattern 的候选进入 review/rejected，不直接写入 accepted 图谱。

必要时对 review 候选调用第二次 LLM，但不对所有候选重复调用，以控制成本。

### 4.3 归一与关系治理

合并后的实体保留 alias 和 resolution evidence；关系按规范端点、类型和方向去重，并保留多个 evidence Chunk。关系正确率不能以“端点存在”替代，必须在评估集中人工判断语义方向和类型。

### 4.4 增量与重建

每次文档入库生成 extraction run 标识。重建或删除文档时按 run/document provenance 清理候选、实体、关系和社区结果，避免旧结果残留。未来可借鉴 Graphiti 的 episode/invalidation 思路，但当前不引入完整时序模型。

## 5. API 与前端设计

### 5.1 Graph API

在现有全图接口之外增加可组合查询参数或子路径：

- `documentId`、`entityType`、`communityId`；
- `minConfidence`、`includeReview`；
- `centerEntityId`、`depth`、`limit`；
- 社区摘要、节点重要性、证据 Chunk 和别名信息。

默认接口只返回 accepted 的有限子图；全图查询保留为调试/管理员能力。

### 5.2 GraphView

- 首屏显示文档/社区概览，不直接展开全部实体。
- 点击或双击节点加载一跳邻域，支持继续展开和返回。
- 节点颜色按实体类型或社区，大小按综合重要性。
- 边标签仅在选中、悬停或侧栏中显示。
- 过滤和搜索保持稳定节点位置，不因切换开关随机重排。
- 侧栏展示规范名、别名、类型、置信度、关系证据和原始 Chunk。
- 对 review 节点/关系提供明确的待确认视觉状态，而不是与 accepted 混在一起。

## 6. 评估与验收

第一条工作线先建立可复现的人工标注和自动指标：

- entity recall ≥ 70%；
- entity precision 目标 ≥ 70%；
- relation semantic correctness 目标 ≥ 70%；
- code/noise false-positive rate 目标 ≤ 5%；
- accepted entity/relation provenance coverage = 100%；
- alias/entity-resolution accuracy 目标 ≥ 90%。

指标必须分文档类型统计，并报告 pooled 与 macro；关系“端点可解析率”只能作为辅助指标。新增固定样本包括 Markdown 正文、代码块、配置、日志、表格、中英文别名、缩写、路径和错误关系。

前端验收包括：稳定布局、局部展开、过滤、证据面板和 review 状态测试；构建和 TypeScript/lint 继续作为质量门禁。

## 7. Worktree 执行顺序

主仓库 `D:\AgenX\archigraph-kg` 只负责规格、评审、合并和任务记录。实现线按依赖顺序建立同级物理 worktree：

| 顺序 | 分支 | 主要范围 | 依赖 |
| --- | --- | --- | --- |
| 1 | `feat/kg-evaluation` | 精确率、噪声率、关系语义和解析分流评估基线 | main |
| 2 | `feat/kg-parsing` | Markdown/文本内容分类与 provenance 元数据 | evaluation |
| 3 | `feat/kg-extraction` | 严格 Schema、证据字段、关系 pattern、候选裁剪 | parsing |
| 4 | `feat/kg-resolution` | 别名、跨文档实体消歧、关系治理 | extraction |
| 5 | `feat/kg-community-api` | 社区/重要性、子图过滤与渐进展开 API | resolution |
| 6 | `feat/graph-experience` | 稳定布局、社区视图、邻域展开、证据面板 | community-api |

每条工作线必须：先写失败测试，再实现；只修改声明范围；更新就近 DEVLOG；在自己的分支提交；由 main 完成独立复审和合并。新增依赖须先记录用途并确认后加入 `requirements.txt` 或前端锁文件。

## 8. 参考实现

- Neo4j GraphRAG Python：Schema、Graph Pruner、Entity Resolver、Structured Output。
- LlamaIndex PropertyGraph：严格实体/关系集合与验证 pattern。
- Microsoft GraphRAG：TextUnit、实体/关系描述归并、社区发现与局部/全局查询。
- LightRAG：多种切块、角色化模型、来源限制和增量管理。
- OpenSPG/KAG：布局分析、属性标准化、语义对齐、知识块双向索引。
- Graphiti：episode provenance、事实失效和混合检索的后续借鉴方向。

