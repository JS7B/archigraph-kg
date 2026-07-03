# 设计规格：体验升级批次（回答区 Markdown 化 · 图谱质量 · AgentRoom 生命感）

> 2026-07-03 大脑窗口经 brainstorming 流程与用户逐节确认定稿。
> 执行拆分见 `tasks/handoff-backend-extraction-quality.md` 与
> `tasks/handoff-frontend-answer-graph-agentroom.md`（工人面向的操作清单，以本规格为准绳）。

## 背景与目标

用户对现状的三点不满：① 回答区 Markdown 原样显示、换行折叠、文字挤成一团；
② 图谱实体抽取机械粗糙（噪声实体入图 + 召回 57.1% 未达 70% 指标）；
③ AgentRoom 像素小人可用动作稀少（入库动作因板块隔离永不触发，仅剩问答检索/打字）。

目标：一次批次内把三处体验拉到「精致可展示」水平，作为简历项目的门面质量。

## 已确认决策（含理由）

| 决策 | 结论 | 理由 |
|---|---|---|
| 回答区渲染 | 引入 react-markdown + remark-gfm | 回答是产品门面；一行 CSS 只能救换行救不了列表/粗体 |
| 引用角标 | 正文内联可点芯片 + **保留末尾汇总行** | 用户选定：角标随句可点，末尾留总览入口 |
| 抽取框架 | **不引入**（MS GraphRAG / LlamaIndex / neo4j-graphrag-python 均否决） | 根因在 prompt 而非框架；保留项目级控制权；自研链路是简历叙事核心 |
| 图谱展示 | 保留 Cytoscape.js，新增 cytoscape-fcose 布局 | 轻量扩展、大图布局质量显著优于内置 cose |
| 写入过滤 | 不做硬过滤，只写 mentionCount | 防召回回退；降噪交给展示层排序/过滤 |
| 孤立节点 | 前端「隐藏孤立节点」开关**默认开** | 孤立点是噪声观感主源；一键可切回全貌 |
| AgentRoom 档位 | **中档：行为队列状态机**（用户三选一选定） | 配角但精致的平衡点；轻档做不出叙事感，重档喧宾夺主 |
| AgentRoom 范围 | 不复活入库动作、不提升全局常驻 | 用户明确拍板（全局常驻易与视图布局冲突） |
| AgentRoom 视觉 | 工人窗口用 ui-ux-pro-max / frontend-design 技能做房间与小人视觉升级 | 用户补充要求；质量基线=「拟人档案管理员、高级精致方向、深紫夜间小剧场对比浅色工作台」 |
| 新依赖 | react-markdown / remark-gfm / cytoscape-fcose（已由大脑安装入 main，0 漏洞，tsc 通过） | 用户批准；无后端新依赖 |

## 设计要点

### 1. 回答区（前端 F1）

- ChatThread 回答正文改 react-markdown 渲染（remark-gfm；不启用 raw HTML，默认安全）。
- 角标方案「预处理 + 组件覆写」：渲染前正则把 `[n]` 替换为 `[[n]](#cite-n)` 链接语法，
  覆写 `a` 组件——`#cite-` 前缀渲染为内联引用芯片，点击复用现有按钮逻辑
  （CitationPanel 高亮 + 滚动定位）。末尾保留「本回答引用：[1][2][3]」汇总行（同一芯片组件）。
- 配套：用户消息 `white-space: pre-wrap`；代码块/表格 `overflow-x: auto`；
  历史会话回灌同路径生效。
- 后端仅在 `qa/prompt.py` 补输出格式指示（Markdown 短段落/列表、角标紧跟句尾），
  不碰 `\[(\d+)\]` 净化正则。

### 2. 图谱质量（后端 B1-B6 + 前端 F2）

- 后端六项：prompt 重写（封闭类型集/排除清单/枚举展开/中英混合 few-shot）、
  归并 key 去 type、Entity 写 mentionCount、图谱 API 度数降序 + degree/mentionCount 字段、
  评估扩全量 4 篇 + 未匹配清单、问答格式指示。细节见后端交接清单。
- 前端 F2：节点尺寸/颜色按度数分级（后端字段优先、edges 兜底计算不阻塞）、
  隐藏孤立节点开关默认开、实体列表度数降序 + 类型 Chip、fcose 布局。
- 验收硬指标：实体召回 ≥ 70%（全量 4 篇），报告让噪声可见。

### 3. AgentRoom 生命感（前端 F3）

- `useAgentPosition` 升级为行为队列状态机：行为 = `{目标工位, 动作, 时长}` 序列，
  保留 rAF 插值与「中断即转」。
- idle 随机剧本：咖啡角喝咖啡 / 踱步 / 发呆 / 打瞌睡(zzz)，加权随机、间隔 8~20s、
  `prefers-reduced-motion` 静止。
- 工作 stage 循环编排：searching＝档案柜翻找→抱文件走回→桌前翻阅（循环）；
  linking＝连线台比划；checking＝桌前翻页；writing＝打字+偶尔挠头伸懒腰；error＝抖动。
- 新道具：手中文件、zzz 气泡。视觉升级用 ui-ux-pro-max / frontend-design 技能执行。
- **红线**：stage 判定只来自 useRunEvents 真实事件；演出是 stage 内部表现层编排，
  不得显示虚假阶段文案；瞌睡/闲逛只在真实 idle。
- 配套：linking 文案改「扩展图谱线索」；`前端说明.md` §8 同步。

### 4. 分工 / 顺序 / 风险

- 后端工人（feat/backend）：B1-B6；前端工人（feat/frontend）：F1 → F2 → F3。
- 两线无代码交叉；共享 Neo4j 错峰（后端清库重建评估数据时段前端避让）。
- 错误处理基线：渲染层对非法 Markdown 兜底为纯文本段落；图谱字段缺失时前端回退
  edges 本地计算；行为状态机在 stage 突变时立即中断当前行为（沿用中断即转）。
- 测试：后端每项带 pytest；前端 tsc/build + 真实问答手测清单 + StyleGallery 预览。
