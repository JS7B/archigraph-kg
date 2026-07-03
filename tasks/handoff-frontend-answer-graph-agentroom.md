# 交接清单（前端工人 · feat/frontend）：回答区 Markdown 化 + 图谱展示分级 + AgentRoom 生命感

> 大脑 2026-07-03 签发，设计规格见 `docs/superpowers/specs/2026-07-03-experience-upgrade-design.md`。
> 开工前：① 把最新 main 合进 feat/frontend（依赖 main 上的依赖安装提交与 `6d0d778`）；
> ② 在 worktree 里重新 `npm install`（react-markdown / remark-gfm / cytoscape-fcose
> 已进 package.json，worktree 的 node_modules 需自行同步）。
> 完成后本地 commit 通知大脑评审。**不碰 main、不自行合并。三个任务按 F1 → F2 → F3 串行。**

## F1 回答区 Markdown 化 + 引用角标内联

背景：回答正文目前纯文本插值（`ChatThread.tsx:45` 附近），`.answerText` 无 `white-space`，
换行折叠、Markdown 原样显示；角标两套并存（正文纯文本 [n] + 末尾按钮排）位置对不上。

1. 回答正文改 `react-markdown` 渲染，插件 `remark-gfm`；**不启用 raw HTML**（默认行为，
   不要加 rehype-raw）。非法/意外输入自然降级为纯文本段落即可，不做额外防护层。
2. 角标「预处理 + 组件覆写」：渲染前用正则把正文 `[n]` 替换为 `[[n]](#cite-n)` 链接语法；
   覆写 `components.a`——`href` 带 `#cite-` 前缀的渲染为**内联引用芯片组件**，点击行为
   复用现有末尾按钮逻辑（CitationPanel 高亮对应证据 + 滚动定位）；其余链接照常渲染
   （建议加 `target="_blank" rel="noreferrer"`）。n 超出 citations 范围时渲染为普通文本。
3. 末尾按钮排改为「本回答引用：[1] [2] [3]」**汇总行**（用户选定保留），复用同一芯片组件。
4. 配套样式：用户消息气泡 `white-space: pre-wrap; overflow-wrap: break-word`；
   Markdown 产物中代码块/表格外层 `overflow-x: auto`；列表/段落间距对齐 tokens.css 尺度。
5. 历史会话回灌（`WorkbenchView` 的 `toChatMessages`）走同一渲染路径，确认新旧消息一致。

→ 验证：tsc/build 零错误；真实问答含「有序列表 + 粗体 + 多角标」的回答渲染正确、
角标可点且定位正确；切会话回灌历史同样正确。

## F2 图谱展示分级降噪

背景：`GraphView.tsx:144` 全量平铺渲染，后端列表按名字排序，孤立噪声节点与核心节点
视觉权重相同——「机械粗糙」观感的展示层成因（后端抽取质量另线并行修）。

1. 布局换 `cytoscape-fcose`（`cytoscape.use(fcose)` 注册；该包无官方 TS 类型时用
   `declare module 'cytoscape-fcose'` 兜底声明）。
2. 节点视觉分级：尺寸与颜色深浅按**度数**映射（2-3 档即可，不做连续插值）。度数来源：
   后端将提供 `degree`/`mentionCount` 字段（feat/backend 并行任务 B4），**未就绪前用
   graphData.edges 本地计数兜底**——写成一个 selector 函数，后端字段到位后一处切换。
3. 「隐藏孤立节点」开关，**默认开**：度数为 0 的节点默认不渲染，开关一键切回全貌；
   开关状态放本地 state 即可，不持久化。
4. 右侧实体列表按度数降序排列，每项带类型 Chip 与度数；与画布选中联动逻辑保持不变。

→ 验证：样本数据肉眼验收——核心实体（高度数）明显突出、孤立点默认不可见、
开关切换正常；空图/单节点边界不报错。

## F3 AgentRoom 生命感（中档：行为队列状态机）+ 视觉升级

背景：小人可用动作只剩问答链路 6 个 stage 的静态站位；用户拍板**不复活入库动作、
不提升全局常驻**，改做「stage 内部的演出编排」。

### 行为状态机

1. `useAgentPosition` 升级为**行为队列状态机**：行为 = `{目标工位, 动作, 时长}` 序列；
   保留现有 rAF 插值与「中断即转」（stage 突变→丢弃当前队列、以真实当前位置为起点执行新剧本）。
2. **idle 随机剧本**（加权随机，行为间隔 8~20 秒）：走到咖啡角喝咖啡 / 房间内踱步 /
   原地发呆 / 打瞌睡（zzz 气泡）。`prefers-reduced-motion` 时不走动、仅保留呼吸。
3. **工作 stage 循环编排**（循环直到 stage 变化）：
   - searching：档案柜前翻找 → 抱文件走回桌 → 桌前翻阅 → 循环
   - linking：连线台前比划连线
   - checking：桌前翻页核对
   - writing：桌前打字，偶尔挠头/伸懒腰
   - error：抖动（沿用现有红光）
4. 新道具：小人手中文件（搬运段显示）、zzz 气泡（仅瞌睡段）。

### 视觉升级（用户点名要求）

5. 调用 **ui-ux-pro-max / frontend-design 技能**对房间与小人做一轮视觉升级：布局、
   配色层次、光影、道具精致度。质量基线沿用既定方向：**拟人档案管理员人设、
   「高级精致」取向、深紫夜间小剧场与浅色工作台的对比关系**（见 `frontend/前端说明.md` §8）。
   升级是「同一方案做精」，不是推翻重来换风格。

### 红线与配套（必须遵守）

6. **stage 判定数据源不变**：只来自 `useRunEvents` 真实 RunEvent。演出是 stage 内部的
   表现层编排；瞌睡/闲逛只发生在真实 idle；**不得显示任何虚假阶段文案**。
7. 配套清理：sceneMap 中 linking 文案「拉关系」改「扩展图谱线索」；入库相关死 stage
   条目加注释标明「仅 StyleGallery 预览可见，运行时不可达」；`前端说明.md` §8 同步
   新演出系统（修复文档与代码脱节）。
8. StyleGallery 预览页适配新行为（每个 stage 静态展示其剧本首帧即可，不必跑循环）。

→ 验证：StyleGallery 全 stage 预览正常；真实问答观察 searching/writing 循环演出与
stage 切换中断即转；空闲 1-2 分钟观察 idle 随机行为分布合理；开启系统 reduced-motion
后小人不走动；tsc/build 零错误。

## 公共约束

- 每个任务完成单独 commit（信息写清做了什么），便于大脑分任务评审。
- 不引入清单之外的新依赖；不动 `src/types` 的 RunEvent/Stage 契约。
- 完成后按模板补 `frontend/DEVLOG.md`（每任务一条，重点写「为什么这么做」）。
- 共享 Neo4j 错峰：F2 联调需图数据时，先确认后端工人没在清库重建评估数据。
