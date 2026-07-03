# 前端学习记录（DEVLOG）

## 2026-06-17 搭建前端工程脚手架（Vite + React + TS）

- 做了什么：用 Vite 初始化 React + TypeScript 工程，建立设计系统 token、
  数据类型、三视图与设置页占位、像素管理员组件（idle 动作可见），并写好
  启动说明与动画维护指南。

- 这是什么：
  - **Vite** 是前端构建/开发工具。它提供一个极快的本地开发服务器（改代码
    立刻热更新），并在发布时把代码打包成浏览器能高效加载的静态文件。相比
    老一代工具（如 webpack）启动和热更新快很多。
  - **React** 是构建用户界面的库。核心思想是"组件"——把界面拆成一个个可复用
    的函数（如 TopBar、PixelAgent），每个组件根据数据（props/state）渲染出
    一段界面，数据变了界面自动更新。
  - **TypeScript** 是给 JavaScript 加了"类型"的语言。比如规定一个函数必须收到
    `Stage` 类型的参数，写错了编译期就报错，而不是等运行时才崩——这对多人/
    多窗口协作尤其有价值。
  - **CSS Modules** 是一种写样式的方式：每个组件配一个 `.module.css`，里面的
    类名只对该组件生效，不会和别的组件撞名。配合 **CSS 变量**（定义在
    `tokens.css` 的 `--color-accent` 等）集中管理配色和间距。

- 为什么需要：前端是整个项目的"门面"，要把文档入库、问答、引用、图谱、运行
  状态都呈现给人看。先搭好骨架（导航、视图划分、数据类型、设计系统），后续
  填业务逻辑时就有稳定的地基，不必反复调整结构。

- 为什么这么做（选型理由）：
  - **不引 Tailwind，用 CSS Modules + CSS 变量**：项目规范"优先简单稳定"。
    浅色设计系统用一组 CSS 变量就能统一管理，不必引入额外的工具链。
  - **数据类型先行（src/types/）**：后端业务接口还没实现，但前端需要哪些
    数据是清楚的。先把 RunEvent / Answer / Citation 等类型写出来，既是"前端
    数据需求清单"，也让占位组件能带着正确的 props 类型搭起来，后端契约定了
    再填实现，不返工。
  - **像素小人与事件流共享一个数据源（useRunEvents）**：这是硬规则"动画必须
    来自真实 RunEvent"的技术保证——两者读同一份事件，永不脱节。当前钩子返回
    占位空流，预留了接 SSE 的位置。
  - **idle 动作先做出来**：用一个会"呼吸"的分层小人验证 CSS 分层动画方案
    可行，作为后续 11 个状态的样板，避免一次性铺开 12 个动作却跑偏。

- 踩了什么坑：
  - Vite 模板自带 `index.css` / `App.css`，我们的设计系统从 `tokens.css` +
    `global.css` 起，所以删掉模板样式、改了 `main.tsx` 的引入，避免两套样式
    打架。
  - 开发预览开关用 `import.meta.env.DEV` 控制：这是 Vite 注入的环境标志，
    开发时为 true、生产构建为 false——保证手动切 stage 的调试按钮绝不会出现在
    生产里，守住"不伪造状态"的红线。

## 2026-06-18 设计系统精细化 + 共享 UI 基件库（P1）

- 做了什么：把 `tokens.css` 从一套"通用默认"打磨成有层次的设计系统，抽出 7 个
  共享 UI 基件（Button / Card / Panel / Chip / StatusBadge / Eyebrow / DataValue），
  并做了一个 dev-only 预览页（`?preview` 入口）把所有基件和 token 一屏展示出来验收。

- 这是什么：
  - **Design token（设计令牌）**：把颜色、间距、字号、圆角、阴影这些"设计决策"
    抽成一组带名字的变量（如 `--color-accent`、`--space-4`），组件只引用变量、
    不写死具体值。好处是改一处、全局生效，且保证整个界面的视觉是"一套系统"
    而非东拼西凑。
  - **UI 基件（primitives）**：最基础、可复用的界面零件。把"一个按钮长什么样、
    有哪些变体（主/次/幽灵）"在一个地方定义好，三个视图都复用它，而不是每个
    页面各写一遍按钮——这样风格统一、改一次处处变。
  - **字阶（type scale）**：一组成比例的字号层级（12/13/14/15/17/20/25/32），
    让标题、正文、标注之间有清晰的大小关系，而不是随手挑字号。

- 为什么需要：上一轮脚手架的 token 只是"能用"——纯灰中性色、只有两档文字色、
  字号局促、没有阴影和动效。这套默认皮肤会让界面显得"AI 生成的粗糙感"。P1 的
  目标就是先把设计系统做精，后面三个视图直接复用精致的基件，避免做完视图再
  回头返工调样式。

- 为什么这么做（选型理由）：
  - **中性色走"冷调 slate"而非纯灰**：slate 偏一点蓝,更贴合知识图谱/技术工具
    的气质,也和 Notion/Linear 那种暖灰的"既视感"拉开距离——同样是浅色专业,
    但有自己的辨识度。
  - **文字分四档（强/正文/次要/弱）**：精致感很大程度来自"信息有层次"。只有
    两档文字色时,标题和说明挤在一起显得平;四档让眼睛一眼分清主次。
  - **等宽字体作"签名元素"（DataValue 基件）**：本项目的护城河是"引用可追溯",
    chunk ID、文档位置、计数这类"可溯源数据"用等宽字体呈现(像代码),既实用
    又让这套设计系统有了区别于普通 SaaS 的记忆点。
  - **不引网络字体、不引组件库**：仍遵循"简单稳定"——系统字体栈 + 自己写的
    CSS Modules 基件足够,不背额外的加载体积和依赖。
  - **预览页用 `?preview` + `import.meta.env.DEV` 双重门控**：它只是给开发/演示
    看的"样板间",不该进生产路由。和像素小人的调试开关同一招,生产构建里这段
    代码会被 tree-shake 掉(实测 bundle 体积不变)。

- 踩了什么坑：
  - 重构 token 时**只增不删**旧变量名:旧组件（TopBar 等）还在引用 `--radius`、
    `--color-text` 等,所以新系统在补充新变量的同时保留了旧名,避免一改 token
    就让已完成的组件碎掉。改完用一段脚本核对"被引用的变量是否都有定义",确认
    无遗漏再提交。
  - 共享基件要留 `className` 透传:第一版 Button/StatusBadge 没留,导致视图复用时
    没法在外部追加样式/定位。补成"继承原生属性 + className 透传"后,基件才真正
    可组合——这是"基件"和"一次性组件"的关键区别。

## 2026-06-18 三视图静态界面 + mock 数据（P2）

- 做了什么：建了一个 mock 数据层（`src/mocks/`），用它把三个视图填成完整界面——
  问答工作台（对话+引用+事件时间线）、文档库（文档卡片+状态徽标）、图谱探索
  （Cytoscape 渲染实体-关系图+搜索+详情面板），全部复用 P1 的基件与设计 token。

- 这是什么：
  - **mock 数据**：后端 API 还没实现，但前端需要"长什么样的数据"是清楚的。
    先按 `src/types/` 的类型造一批假数据（一篇 Transformer 论文相关的问答、
    文档、图谱），让界面能完整渲染。将来后端就绪，只需把"读 mock"换成"调
    真实 API"，因为数据形状完全一致，几乎零改动。
  - **Cytoscape.js**：一个在网页上画"图"（节点+连线）的库。知识图谱本质是
    实体（节点）和关系（边），Cytoscape 负责把它们布局、渲染成可缩放可点击的
    画布。它直接操作一块 canvas，不是普通的 React 组件树。

- 为什么这么做（选型理由）：
  - **mock 数据集中放一处（`src/mocks/index.ts`）**：而不是散在各组件里。这样
    "假数据"和"真数据"的边界清晰，将来一处替换；也方便所有视图共享同一套
    演示数据，故事连贯（问答问的实体，在图谱里能找到）。
  - **工作台：时间线喂 mock，但像素小人坚持 idle**：这是关键的纪律。`useRunEvents`
    是时间线和小人的"唯一数据源"。如果为了 demo 把 mock 事件灌进它，小人就会
    被假数据驱动——违反硬规则"动画只来自真实 RunEvent"。所以把 mock 事件**只
    直接传给时间线组件**做展示，`useRunEvents` 保持纯净（空→小人 idle）。宁可
    demo 里"小人不动"，也不破红线。
  - **复用 P1 基件而非重写**：三视图里的按钮、卡片、状态徽标、面板全部用 P1 的
    基件。这正是先做 P1 的回报——视图层只管组合，不再各写一套样式，风格天然统一。

- 踩了什么坑：
  - **Cytoscape 在 React 里的生命周期**：React 18 开发模式下 `useEffect` 会被
    故意调用两次（StrictMode，用来暴露副作用 bug）。如果只在 effect 里 `new
    cytoscape(...)` 而不清理，就会留下两个画布实例、内存泄漏。正确做法是 effect
    里返回 `() => cy.destroy()` 做清理，并把"初始化"和"搜索/选中"拆成不同 effect
    ——否则每敲一个搜索字符都会把整张图重建一次。
  - **Cytoscape 的画布读不到 CSS 变量**：它的样式在 JS 里配置、画在 canvas 上，
    拿不到 `var(--color-accent)`。所以图谱样式只能写死十六进制色值——这是唯一
    允许写死颜色的地方，并在每个色值旁注明它对应哪个 token，方便日后同步。

## 2026-06-18 引用面板滚动定位（P3）

- 做了什么：给引用证据面板加上"点击答案里的引用角标 → 面板平滑滚动到对应来源
  条目并高亮"的定位能力，并修正了引用抽屉一个高度 bug。

- 这是什么：
  - **scrollIntoView**：浏览器原生 API，让某个元素滚动进可视区域。配
    `behavior:'smooth'` 平滑滚动、`block:'nearest'` 表示"就近滚动、不过度移动"。
  - React 里要拿到"那个 DOM 元素"得用 **ref**（引用）：把 ref 挂到当前高亮的
    条目上，`activeChunkId` 变化时在 `useEffect` 里调用它的 scrollIntoView。

- 为什么需要：引用可追溯是本项目的护城河。当回答里有多条引用、面板装不下时，
  只"高亮"不够——高亮的条目可能在视口外，用户还得手动找。点角标自动滚到来源，
  才真正做到"一键定位证据"。

- 为什么这么做：
  - **滚动用 `block:'nearest'` 而非 `'center'`**：只在引用抽屉内部就近滚动，不会
    把整页都带着动，交互更克制。
  - **ref 只挂在当前 active 条目上**（`ref={isActive ? activeRef : null}`）：这样
    `activeRef.current` 永远指向高亮项，effect 直接滚它，不必维护一个 ref 数组。

- 踩了什么坑：
  - 修 P2 留下的高度 bug：引用抽屉 `.citation` 的 `max-height` 被写成
    `var(--space-8)`（64px），连一条引用都显示不全，滚动定位更无从谈起。改成
    240px（约可见两条 + 内部滚动），定位能力才有意义。这也提醒：间距 token 是
    给"间距"用的，不该挪用来当"组件高度上限"。

## 2026-06-22 契约层改造：对齐 B 板块异步 + SSE

- 做了什么：把前端从"同步 mock"改成"起异步 Run + 订阅 SSE 进度流"的真实契约。
  新建 SSE 客户端（`api/sse.ts`），改造 `useRunEvents` 接真实事件流，问答/上传/删除
  三个写场景全部改成「起 Run → 订阅 → 驱动 UI」，GET 类（文档列表）也接了真实后端。
  RunEvent/Answer/Citation 类型逐字段对齐后端源码。像素小人本轮保持 idle（动画下一轮）。

- 这是什么：
  - **SSE（Server-Sent Events）**：浏览器原生协议，服务端可以单向、持续地把消息
    推给浏览器（不像普通 HTTP 一问一答就结束）。用 `new EventSource(url)` 建立
    连接，挂 `onmessage` 收消息，`close()` 释放。本项目后端把入库/问答/删除的
    进度（正在解析、正在抽取、回答完成…）一条条推过来，前端据此更新时间线和小人。
  - **异步 Run**：旧契约下 `POST /api/documents` 要等整条入库链路（解析→向量化→
    写图库→抽实体）跑完才返回，前端干等几十秒没有反馈。新契约改成"立即返回
    runId"，后台任务边跑边 emit 事件，前端订阅事件流就能看到实时进度。
  - **终态（terminal）事件**：一条 Run 的最后一条事件，`status='succeeded'`（成功）
    或 `'failed'`（失败）。后端发完它就关闭 SSE 流，前端也要在收到它时关闭
    EventSource——否则连接会一直挂着，积累成"僵尸连接"泄漏资源。

- 为什么需要：B 板块把后端改成异步后，旧前端的所有 mock 调用都按"同步拿到完整
  结果"写的，类型和调用方式全对不上。不先改契约层，后续接真实数据 + 像素小人
  动画都没法进行。这一轮专门把"数据形状"和"调用方式"一次性对齐，是承上启下的地基。

- 为什么这么做：
  - **写操作直连真实后端、GET 类保留 mock**：开发环境后端在 localhost:8000，
    直连最简单（不必再造一套 mock SSE 适配层）。代价是前端开发时要起后端，但
    本项目本就是前后端配套的，可接受。
  - **`useRunEvents(runId)` 保留红线**：`currentStage` 只从真实事件派生，这是
    硬规则"像素 Agent 状态必须来自真实 RunEvent"的技术保证。Hook 签名从无参改
    成接 `runId`，谁订阅谁传 runId，状态来源清晰可追溯。
  - **终态自动关闭 EventSource**：在 `onmessage` 里判到 succeeded/failed 立即
    `source.close()`，`onerror` 也关。后端发完终态会断流，前端再关一次是双保险。
  - **判终态用 `status` 而非 `stage`**：后端成功终态事件的 `stage` 是 `'idle'`
    （"回到待命"），不是 `'done'`。如果用 stage 判就会漏掉终态，导致订阅永不结束。
  - **`timestamp_ms` 用下划线**：后端 `RunEvent.timestamp_ms` 字段没加 camelCase
    alias，序列化输出就是下划线名。前端类型直接用 `timestamp_ms`，省一层转换、
    和后端源码一一对应、少踩坑。
  - **上传用原生 fetch 而非 apiFetch**：multipart 上传（FormData）的 Content-Type
    必须由浏览器自动带 boundary，而 `apiFetch` 会强制设 JSON content-type，会破坏
    multipart 边界。所以上传这一处绕过 apiFetch 直接用 fetch + 共享的 BASE_URL。
  - **本轮不做断线重连 + /events 历史补全**：简单优先。EventSource 自带断线重连，
    下一轮如需补全再加 `/events` 一次性取回历史事件的兜底。

- 踩了什么坑：
  - **规格文字与后端实际契约不一致**：规格里写终态 `stage='done'`、`Answer` 带
    `question`、`Citation` 带 `documentName`，但读后端源码发现全不一样（终态是
    stage='idle'+status='succeeded'、Answer 无 question、Citation 是 documentId）。
    教训：规格是"意图"，**契约以已验证的后端源码为准**，开工前必须逐字段核对，
    不能照规格文字写代码。本次按后端实际对齐前端类型，并把不一致点记在计划里。
  - **Chip 组件只有 neutral/accent 两档 tone**：LibraryView 里给"进行中"状态提示
    误用了 `tone="info"`，build 报错。Chip 不像 StatusBadge 有 info/success/error
    全套语义色——它只是轻量标签。改成 accent（强调进行中）即解决。这说明共享基件
    的"能力边界"要心里有数，别假设它和别的基件一样全。

## 2026-06-23 像素档案员精细版 + 12 状态动画（P0）

- 做了什么：把像素小人从 6 层 48×64 占位，升级成 22+ 层 96×144 的精细分层 CSS 小人，
  并为全部 12 个执行状态实现了带场景道具的动作动画。这是 P0（原本约定用户亲调，
  经授权改由代理接手）。验证页 `?preview` 新增 12 状态全览网格。

- 这是什么：
  - **CSS 分层动画**：小人是 22+ 个绝对定位 div（头/五官/躯干/四肢/脚/影子/道具），
    每个部件是一个可独立动画的层。动作靠 CSS `@keyframes`（如手臂 rotate、身体
    translateY），不需要逐帧图片或 canvas。这是"方案 B"，对比过 sprite 帧动画后选定。
  - **`data-stage` + `data-part` 选择器协作**：module.css 定义部件静态形态（类名会被
    Vite hash 化），全局 animations.css 用 `[data-stage="x"] [data-part="y"]` 选中部件
    做动作。data-* 属性不被 hash，是两套 CSS 协作的稳定桥梁。
  - **像素精细度**：放大画布给细节留像素空间，加描边/高光/阴影做体积感，五官齐全
    （眉/双眼/眼镜片框+反光/鼻/嘴）、头发鬓角、躯干前后片、双腿双脚、场景道具
    （桌面/咖啡杯冒蒸汽/碎纸机/复印机/放大镜）。

- 为什么需要：像素小人是项目的前端记忆点，硬规则要求"动画状态必须来自真实
  RunEvent"。之前只有 idle 一个真动画、其余 11 个是占位抖动，既看不出 Agent 在干嘛、
  也接不上后端 SSE 推来的 stage。这一轮把 12 状态全部做精细，让小人真正"会干活"。

- 为什么这么做（选型理由）：
  - **方案 B（精细 CSS）而非 sprite 帧动画**：先做了 sprite 可行性验证（纯 Node 编码
    PNG + 浏览器逐帧播放），技术上可行，但三个硬伤让它不适合本项目：① 代理看不到
    渲染效果、98 帧盲调无法做精细；② sprite 是二进制资产、改一帧要重新生成整张图；
    ③ 与项目零图片资源、颜色走 design token 的体系冲突。CSS 方案实时可控、我能
    精确调每层、你也能即时看效果，是更优解。
  - **分发子代理并行设计动作**：12 状态按语义分 4 组（入库/图谱/问答/删除维护），
    4 个子代理并行产出各组的 CSS 动画片段，我再整合成统一 animations.css。子代理
    价值在于并行设计动作方案，但它们同样看不到渲染，故最终视觉仍需预览页确认。
  - **module.css 与全局 animations.css 分工**：静态形态用 CSS Module（类名 hash、
    作用域隔离），动作用全局 CSS（`[data-stage]` 选择器、不被 hash）。这是关键架构
    决策——让"形状"和"动作"解耦，子代理加动作时只动 animations.css、不碰 module.css
    的类名映射，避免合并冲突。
  - **heldProp（手持道具）DOM 常驻**：放大镜/标签/碎纸机等道具不随 stage 切换重建
    DOM，而是常驻、由 `data-stage` 控制显隐。避免 stage 切换时道具闪现/动画跳变。

- 踩了什么坑：
  - **CSS Module 类名被 hash，全局 CSS 选不中**：最初想用类名（`.armL`）在全局
    animations.css 里定位部件，但 Vite 把 module 类名 hash 成 `._armL_abc123`，全局
    CSS 写 `.armL` 匹配不到。解决：给每个可动画部件加 `data-part` 属性（稳定不 hash），
    全局 CSS 改用 `[data-part="armL"]` 选中。这是 CSS Module + 全局 CSS 协作的标准做法。
  - **子代理产出的 keyframe 名冲突**：4 个子代理独立设计，撞名了 `pa-blink`（叹号闪烁
    vs 眨眼）、`pa-nod`（不同点头参数）、`pa-rest-l/r`（不同扶机动作）。整合时按语义
    重命名（pa-bang / pa-search-nod / pa-delete-nod / pa-hold-l/r）去重。教训：并行
    产出必须由主代理统一命名空间、做冲突消解。
  - **验证产物误放 public/ 会进生产构建**：sprite 验证页一开始放在 `frontend/public/`，
    这个目录会被 Vite 打进生产包。及时发现并移到仓库根的 `.sprite-probe/`（脱离前端
    工程、不进构建、未跟踪）。public 不是"随便放文件的地方"，它是生产静态资源目录。

## 2026-06-24 AgentRoom 房间式改造（方向转变：废弃精细角色路线）

- 做了什么：把工作台侧栏的精细 `PixelAgent`（22+ 层 CSS 小人 + 12 套逐帧动画）整个废弃，
  换成 `AgentRoom`——一个深紫调像素小房间，里面一个极简悬浮色块小人，状态靠**头顶气泡
  + 周围场景道具**叙事。删除旧 PixelAgent 目录，WorkbenchView + StyleGallery 全部接入新组件。

- 为什么方向变了（关键决策记录）：
  - 上一轮精细角色路线（五官/发型/眼镜/手臂合并/五官精修）走不通：CSS 拼 22+ 层精细小人
    观感始终不达标（圆角化、大头胖身细腿、细节糊），且 12 套逐帧动画的手臂/手脱节问题难根治。
    大脑与用户商议后判定废弃，改为 ZCodeRoom 式「极简小人 + 场景叙事」。
  - ZCodeRoom 是用户在另一个项目（依赖 ZCode+GLM 设计）上做好的原型，设计成熟、直接复用。
    核心理念：**小人弱化为会呼吸的色块，"它在干嘛"全靠它周围发生的事讲**——成本低、耐看、
    好维护、无需美术资源。这是降维：用「场景道具变化」替代「角色自身复杂动画」。

- 这是什么：
  - **box-shadow 像素法**：用 1 个 div + 多层 `box-shadow` 画小人全部像素（每个 box-shadow
    是一个色块，偏移定位）。比"逐格生成 64 个 div"性能好（DOM 节点少）。
  - **像素编译器折中**：纯手写 box-shadow 坐标极难维护。我写了 `drawDude.ts`——用 8×8 网格
    字符串数组（如 `'.gseseg.'`）作单一数据源，启动时 `compile()` 把它编译成 box-shadow 字符串。
    改图案/配色只改易读的 pattern/常量，box-shadow 自动生成。兼顾性能和可维护性。
  - **场景道具叙事**：12 个状态，小人本体几乎不变（只 bob 浮动 + 工作时摆动 + error 抖），
    变的是头顶气泡图标 + 周围道具（文档飞入、碎纸机吸入、放大镜扫描、档案柜抽屉开合…）。
  - **data-stage 驱动**：道具 DOM 常驻，CSS 用 `[data-stage="xxx"] .p-xxx { opacity:1 }`
    控制显隐，避免切换时 DOM 重建导致动画跳变。

- 为什么这么做：
  - **修大脑原型 4 个已知问题**：① 道具不遮挡小人（碎纸机/档案柜等大道具从正中移到小人
    右/左侧）；② 小人放大（32×36，有腿更敦实）；③ 房间加常驻场景（桌子/显示器/门，让
    小人"有个家"）；④ 小人对齐 ZCodeRoom（网格画法 + 配色，卫衣改本项目蓝靛紫主色）。
  - **配色走 design token**：房间紫调/小人/道具色都新增到 `tokens.css`（`--room-*`/`--dude-*`/
    `--prop-*` 语义 token），不散落硬编码。只有 box-shadow 编译器里小人色硬编码（因 box-shadow
    字符串无法引用 CSS 变量），用注释标明对应 token。
  - **删旧留新**：PixelAgent 目录整个删（git 留历史），`Stage` 类型在 `types/runEvent.ts`
    独立不受影响。`useRunEvents` 红线不变（stage 只来自真实 RunEvent），DEVLOG 注释更新。

- 踩了什么坑：
  - **CSS Module 与全局 CSS 的 class 命名协作**：道具用全局 class 名（`prop p-upload`，不经
    module hash）才能让全局 `roomScenes.css` 稳定选中。若道具 class 走 `styles.prop`（hash），
    全局 CSS 写 `.prop` 选不中——这是 CSS Module 项目的经典坑，和上轮 PixelAgent 的
    data-part 方案同理（用不被 hash 的标识做桥）。
  - **房间 DOM 结构重构**：初版把房间画布和状态栏都放在 `.room` 根节点，导致定位锚混乱。
    重构为 `.room`(flex 容器) > `.canvas`(固定 220 高，承载场景) + `.status`(正常流)，
    data-stage 挂在 `.canvas` 上（场景元素都在其内）。教训：容器职责要单一——`.room` 管面板
    外观，`.canvas` 管画布定位，分开才不互相干扰。

## 2026-06-24 真实 API 接入收尾（GraphView + SettingsView）

- 做了什么：把仍在用 mock/占位的两块接到真实后端——GraphView 接 `/api/graph/*`、
  SettingsView 实现（接 `/health/deps`）。新建 api 领域层（graph.ts + health.ts）做后端调用
  + 字段映射收口。AgentRoom 道具遮挡复查确认上轮已修、本轮无需改动。

- 这是什么：
  - **api 领域层**：把"调后端 + 字段映射"收口在 `src/api/` 下的领域文件里
    （graph.ts/health.ts），View 层只认前端类型（GraphData 等），不关心后端字段名。
    这与现有 api 层（按传输机制分 client/sse）风格略不同（更按领域），但对字段
    不一致的 GraphView 改造更干净。
  - **字段映射**：后端 graph 路由返回的 `{nodes:{id,name,type}, edges:{source,target,type}}`
    与前端 `types/graph.ts` 的 `{id,label,entityType}/{id,source,target,relationType}` 字段
    名不一致。映射在 graph.ts 里做（name→label、type→entityType/relationType），后端 edge
    无 id 则用 source-target-type 生成。View 层完全不感知这层差异。

- 为什么需要：前端大部分已接真实 API（文档库/问答/引用/事件流），但 GraphView 还在用
  mockGraph 硬编码、SettingsView 还是占位。这两块接通后，整个工作台才端到端真跑通——
  上传文档能看真实图谱、设置页能看依赖状态。

- 为什么这么做：
  - **GraphView 三态（loading/error/空图）都处理**：学了 LibraryView 的 refresh+useEffect
    模式，但补了它缺的 loading flag（LibraryView 首次渲染 documents=[] 会误显示"空列表"，
    GraphView 拉图谱慢，必须区分"加载中"和"真空图"）。Cytoscape 容器只在数据就绪后渲染，
    避免空容器闪烁。
  - **Cytoscape init useEffect 依赖改 [graphData]**：原来是 `[]`（挂载一次、用静态 mock）。
    改成依赖 graphData 后，数据到位才建实例、数据变了会重建（destroy 旧的建新的）。
    没用 cy.add/remove 增量更新——简单优先，全量重建对 limit=100 的样本规模无性能问题。
  - **搜索仍走前端 filter**：不调 /api/graph/search API。因为搜索是在已渲染的 Cytoscape
    实例上做 label 高亮，体验即时；调 API 反而慢且要重建图。search API 留给未来"跨页搜索"
    场景。这是"用对的工具"——搜索 API 适合返回列表的场景，不适合图谱高亮。
  - **字段映射放 api 层而非 View**：如果放 View，GraphView 会混入后端字段名，且
    findGraphNode/getNodeRelations 也要处理两种字段。收口在 graph.ts，View 和本地函数
    都只认 GraphData，干净且可测。

- 踩了什么坑：
  - **后端 edge 无 id，前端需 id**：Cytoscape 的 element 和 React 的 key 都需要唯一 id，
    但后端 RELATES 边只返回 {source,target,type}。用 `${source}-${target}-${type}` 生成
    稳定 id（同一关系多次拉取 id 一致，不破坏 React reconciliation）。教训：跨端字段
    不只是"名字不同"，还可能"有缺"，映射层要兜底补全。
  - **CSS Module 里 `:global(code)` 影响范围过大**：SettingsView 初版想给 `<code>` 加背景
    样式，写了 `:global(code){...}`——这会让全 app 的 code 都加背景，污染其他视图。
    发现后删掉，改用全局已有的等宽字体（global.css 里 code 只设了 font-family）。
    教训：CSS Module 的 `:global` 是逃生舱，慎用——它穿透作用域，影响全局。

## 2026-06-26 AgentRoom 场景叙事重构（悬浮小人 + 家具运转）

- 做了什么：把 AgentRoom 从「静态小人 + 大道具盖住小人」重构为「小人按状态横向
  飘到对应家具工位前 + 家具自身运转表达动作」。小人配色恢复多彩（橙卫衣+粉高光），
  咖啡杯缩小，去掉 devControls 切换按钮与 emoji 气泡（AI 味来源）。前端零后端改动。

- 这是什么：一次纯前端的动效表达策略升级。把"动作"的载体从「小人摆 pose」换成
  「小人位移 + 道具运转」——符合像素动画正道（角色整体位移用连续补间平移），
  又避开了"不做手臂逐帧"的难题。

- 为什么需要：上一版小人全 12 状态本体完全相同，只靠 emoji 气泡 + 盖在身上的大道具
  区分，既沉闷（单色蓝靛紫）又挡主体（碎纸机/档案柜压住小人）。根因是"小人当主体但
  没投入主体该有的动作可辨识度"。本次按"小人是配角、工作台才是主体"重新定调。

- 为什么这么做（取舍）：
  - **横向飘移到工位**而非原地动作：5 个家具 = 5 个工位（电脑桌/咖啡角/打印机/档案柜/
    销毁台），12 状态归类映射。小人用 `transition: left 0.8s` 连续补间平移，这是像素
    动画认可的角色位移做法。
  - **"喝咖啡"绕过手臂**：idle 状态小人在电脑前↔咖啡杯之间循环飘，飘到杯口时身体微
    压低（凑近喝），而非"手举杯"——读得出动作但不渲染手臂。
  - **去掉 emoji 气泡**：那是 AI 偷懒的典型（用 emoji 冒充图标），动作信息改由"小人飘到
    哪 + 道具怎么转"完整表达，气泡纯属冗余。
  - **多彩配色**：橙卫衣让小人成为深紫房间的视觉锚点，跳出来不沉闷；与主区靛紫不撞色。

- 踩了什么坑：
  - 重写 sceneMap 时漏删/漏留 `ALL_STAGES` 导出（StyleGallery 在用），导致 `tsc -b`
    报 TS2305。教训：删导出前要全项目 grep 引用；`tsc --noEmit` 和 `tsc -b` 严格度
    不同，build 的 `-b`（project references）更严格，验证务必跑 build 不只 typecheck。
  - roomScenes.css 里 `[data-stage="x"].dude` 漏写空格（应为 `] .dude`）会让选择器失效、
    小人在该状态不飘移。CSS 属性选择器与 class 之间必须有空格。

## 2026-06-28 PR 审计整改 F1-F15（无障碍/响应式/契约）

- 做了什么：按 PR 审计 §5 报告分四批整改前端（F0/F-契约 契约、F1-F7 无障碍
  CRITICAL、F8-F11 响应式+交互 HIGH、F13/F14/F15 加分项）。F12 经评估跳过。

- 这是什么：一次面向"简历硬规则 + 公开展示质量"的无障碍/体验系统整改。
  报告依据 ui-ux-pro-max 十类规则，CRITICAL 项关系到简历可信度。

- 为什么需要：前期专注功能跑通，无障碍/响应式欠账较多。GraphView 的 canvas
  不可键盘访问、TopBar 状态灯是占位、颜色对比度不达 AA、缺主标题语义等，都是
  公开仓库/简历展示的硬伤。

- 为什么这么做（关键决策）：
  - **契约同步（F0/F-契约）**：后端 B2/B8 已先改（X-API-Key + timestampMs alias），
    前端跟着切。SSE 因 EventSource 不支持自定义 header，开发模式无影响，生产需
    后端放行 /events/stream——在 sse.ts 标注隐患而非硬上 fetch-based 重写（简单优先）。
  - **F5 用数据表补偿 canvas 不可达**：Cytoscape canvas 节点无法 Tab 访问，与其重写
    键盘导航，不如在实体详情空状态补一个可 Tab 的实体按钮列表，复用已有选中逻辑，
    最可靠。
  - **F6 焦点管理用 activeElement 而非跨组件 ref**：设置触发按钮在 TopBar 深层，
    App 拿不到它的 ref；用 document.activeElement 在打开时记录、关闭时还原，模式
    干净不依赖组件树形状。
  - **F12 跳过**：家具 hex 提取 token 收益低（纯整洁度），AgentRoom 颜色已集中，
    过度提取违背简单优先。等真有多处复用需求再做。
  - **F13 只做"屏幕发光仅 busy 时跑"，不改 idle bob 节奏**：0.6s 悬浮经调试已舒适，
    改 0.4s 会让悬浮显焦躁——审美风险 > 收益。

- 踩了什么坑：无重大踩坑。`tsc --noEmit` 与 `tsc -b` 严格度差异（前者宽、后者严）
  此前已吃过亏，本轮每批都跑 build 验证。

## 2026-06-29 多会话多轮对话记忆（前端 UI + mock 打通）

- 做了什么：把工作台从「每次提问孤立单轮」升级为多会话多轮对话。新增会话侧边栏
  （列表/新建/切换/删除带二次确认）、三列布局、会话状态管理、历史消息回灌。
  后端会话 API 未就绪，先用本地 mock 打通 UI 与状态流（api/conversations.ts 的 USE_MOCK）。

- 这是什么：一次"会话持久化"的前端改造。原先 messages state 是内存态、刷新即丢、
  后端也不感知历史；现在引入 Conversation 维度，让"连续追问记住上文""切换会话恢复历史"
  成为可能。

- 为什么需要：单轮问答无法体现 Agent 的记忆能力，多轮对话是 RAG 工作台的基础体验。

- 为什么这么做（关键决策）：
  - **mock 开关收口在 api 层**：USE_MOCK 集中在 conversations.ts，UI 完全走真实流，
    后端就绪后改一个常量即切真实，不用动组件。提问链路（/api/chat）不 mock——它本就
    要等真实后端，mock 它会掩盖真实联调问题。
  - **三列布局而非两列+抽屉**：会话列表是常用功能，固定侧边栏（240px）比抽屉更直接。
    窄屏（<860px）侧边栏自身折叠成 max-height 200px 的横条。
  - **ConversationMessage → ChatMessage 转换复用现有渲染**：让历史消息的引用角标、
    CitationPanel 逻辑零改动（agent 消息还原成 {text, confidence, citations}）。
  - **删除二次确认用自定义 dialog 而非 window.confirm**：保持风格统一 + 键盘可达
    （autoFocus 确认按钮、Esc 取消路径可后续补）。

- 边界（讲清楚，避免误用）：
  - mock 模式下提问会失败（后端未就绪），这是预期的——mock 只打通会话 UI 流。
    （后记：后端就绪后 USE_MOCK 已改 false 并删除整段 mock 数据，本条记的是 mock 阶段的工作。）
  - 终态后只清 chatRunId 解除 busy，不清 conversationId（关键，否则追问会断）。
  - refreshList 在终态后调用刷新侧边栏 messageCount/title，可能有轻微闪烁，可接受。

- 踩了什么坑：无重大踩坑。Button 组件只支持 primary/secondary/ghost，没有 danger variant，
  删除确认按钮改用 primary（设计系统暂无红色按钮 token，强行加会破坏一致性）。

## 2026-06-30 工作台布局重排 + 文档删除确认 + 会话状态保持

- 做了什么：三件独立体验修正。① 引用证据面板从中列移到右列（对话区变大）；
  AgentRoom 下方状态文字替换为 RunEventTimeline 运行轨迹。② 文档删除改为弹窗
  二次确认，确认后才带 confirm=true 调后端。③ 视图切换改 CSS hidden 常驻，
  切走再回来会话/对话历史不丢。

- 这是什么：一次围绕"主对话区可用性"的体验修正，解决前两轮功能开发累积的三个痛点。

- 为什么这么做（关键决策）：
  - **引用面板挪右列、轨迹进 AgentRoom**：原中列塞三块（对话+引用+输入），引用面板
    占 240px 挤得对话区很小。挪走后对话区独占中列；AgentRoom 下方原本只是静态状态
    文字，换成实时运行轨迹更有信息密度。轨迹用浅色面板嵌入深色房间，视觉不突兀。
  - **删除确认复用 ConversationSidebar 的 modal 风格**：不抽共享 ConfirmDialog 组件——
    目前只有两处用（会话删除/文档删除），内联更直接；待第三处出现再抽，符合简单优先。
  - **CSS hidden 常驻替代条件渲染**：原 `{view==='workbench' && <WorkbenchView/>}`
    切走即卸载、state 全销毁。改 `<div hidden={view!==...}>` 常驻，组件不卸载、state
    天然保留。比"提升 state 到 App"零改动 WorkbenchView，最简单。
  - **GraphView 不加 active prop**：核实它无轮询（只 mount 时拉一次），Cytoscape 常驻
    只占内存不发请求，闲置内存可接受。若实测卡顿再加。

- 边界：sceneMap 的 label/detail 不删（busy 仍驱动 data-busy 动画，只是不再显示文字）。
  红线守：AgentRoom 的 stage 仍只来自真实 RunEvent，events 仅驱动下方轨迹显示。

## 2026-07-02 [已澄清：非 bug] 长任务 SSE「终态丢失」实为任务耗时误判

> ✅ 2026-07-03 更正：此条曾记为「未解决的终态事件丢失 bug」，后经用户实测澄清——
> **终态事件最终会正常到达浏览器**。之前观察到的「进度停在抽取阶段、列表不刷新」
> 只是实体抽取本身耗时很长（逐 chunk 调 LLM，几分钟量级），每次诊断都没等到任务
> 真正结束就下了「事件丢失」的结论。SSE 链路前后端均无 bug。

- 做了什么：为「终态丢失」做了多轮诊断与修复尝试（后端 sleep 延迟关闭、前端
  onerror 历史兜底、放行原生重连 + seq 去重），全部"无效"——因为根本没有 bug
  可修：等任务真跑完，终态事件就到了。后经评审，feat/frontend 的 onerror 历史兜底
  重新定性为**防御性容错**（应对真实断线：网络抖动/服务重启）保留合入 sse.ts，
  注释已同步订正，不再声称"修终态丢失 bug"。

- 这是什么：一次典型的**误诊**。入库的 extracting 阶段逐 chunk 调 LLM 抽实体，
  chunk 多时要跑好几分钟；期间前端进度一直停在最后一个 running 事件（如「抽取
  实体与关系」），看起来像"卡死/丢事件"，实际后台在正常干活。

- 为什么会误诊（复盘）：
  1. 用 Python `requests` 验证后端时，读的是**已完成 Run** 的历史回放——秒回全部
     6 条事件含终态，于是误信"后端能发、浏览器收不到"，把矛头指向协议层。
     正确的对照实验应该是在任务**进行中**开一条 requests 实时流，和浏览器同条件对比。
  2. 浏览器端 console.log 的观察窗口太短：看到 `events.len=4 last=indexing/running`
     后没继续等，就断言"第 5、6 条从未到达"——其实是任务还没跑到那一步。

- 教训（已沉淀为 tasks/lessons.md L8）：诊断「事件没到」之前，先确认「事件该到的
  时刻是否已经过去」——对长任务先量化真实耗时（看后端任务结束时间戳 / 轮询
  `GET /api/runs/{id}` 的 status 何时翻转），确认"后端已终态而前端仍没收到"，
  才轮到协议层排查。

- 残留处理（2026-07-03 清理）：
  - 「刷新列表」「刷新图谱」按钮**保留**——不再承担"绕过 bug"职责，但作为低频
    手动刷新入口仍有价值（多标签页 / 外部改库场景）。
  - 后端 `seq` 字段保留为事件基础设施（无害，日后断线重连去重可用）。
  - sse.ts 保留 onerror 历史兜底（定性为防御性断线容错，非 bug 修复，含退订守卫）；
    前端无调试 console.log 残留；后端无 sleep 延迟残留。
  - 交接文档 `tasks/handoff-sse-terminal-event-bug.md` 已删除（针对不存在的 bug）。

- 可选的后续改进（产品层，非 bug 修复）：extracting 阶段在 UI 上给出耗时预期
  （如"抽取中，视文档大小可能需要数分钟"），从源头消除"卡死"错觉。


## 2026-07-03 修问答/上传"慢一拍"——useRunEvents 事件残留竞态

- 做了什么：`useRunEvents` 把"清空事件"从 effect 里挪到渲染期（`runId` 变化时同步重置）。
  一处改动同时修好两个症状：问答发新问题时显示上一次的回答、上传文档要点第二次才有反应。

- 这是什么：一个 React 状态时序 bug。`useRunEvents(runId)` 累积某个 Run 的 SSE 事件，
  消费方（WorkbenchView/LibraryView）用一个"终态 effect"监听 `events` 的最后一条，
  是成功事件就落成答案/刷新列表，然后把 runId 清成 null 结束订阅。

- 为什么会错（根因）：原来重置 `events` 的代码写在 `useEffect` 里、且被 `if (!runId) return`
  挡在前面。于是 Run 结束（runId→null）时这段重置**永远走不到**，上一轮的成功事件一直
  滞留在 `events` 数组里。等下一个 Run 起来（null→newId），消费方的终态 effect 因依赖
  `runId` 变化被重新触发，而**这一帧它读到的 `events` 仍是上一轮的残留**（新 Run 的
  `setEvents([])` 只是排队、还没生效）。结果：它把**上一轮的答案**当成本轮结果落下，
  同时把刚起的新 Run 订阅拆掉——所以"慢一拍、要再发一次/再点一次"。

- 为什么这么改：用 React 官方的"渲染期随输入变化调整 state"模式
  （`if (runId !== prevRunId) { setPrevRunId(...); setEvents([]) }`）。它在渲染阶段就把
  `events` 清空并触发 React 立即用新 state 重渲染，**早于**任何 effect 运行——所以消费方的
  终态 effect 本帧就能拿到空 `events`，读不到旧事件。备选是在消费方 effect 里判 runId 归属，
  但那是打补丁；根因是事件残留，在数据源头（hook）清才干净，且两个视图共用此 hook，改一处全修。

- 踩了什么坑：症状看起来像"后端返回了旧回答"，实际后端每轮 Run 独立、答案现算现发，
  完全正常——排查时先从后端 RunStore/SSE 确认无跨轮串味，才把方向锁定到前端状态时序。

## 2026-07-03 设置抽屉「打开就滚到底」的根因：focus() 会触发滚动

- 做了什么：修设置抽屉三个问题——打开默认滚到底部、内容双重留白显得臃肿、
  模型配置中英文不对齐；顺带把图谱页详情栏改为 grid 跨行贴顶，消除顶部空白。

- 这是什么：浏览器对 `element.focus()` 有一个默认行为——**自动滚动容器让
  被聚焦元素可见**（scroll-into-view）。我们的抽屉为无障碍做了焦点管理：
  打开时把焦点移到「关闭」按钮上；而这个按钮恰好排在面板最底部，于是
  浏览器"贴心地"把整个抽屉滚到底，看起来就像"默认打开在末尾"。

- 为什么需要：焦点管理本身不能删（键盘用户打开弹层后焦点必须进入弹层，
  这是无障碍硬要求），所以不能靠"不聚焦"来绕过，得让焦点目标的位置合理。

- 为什么这么做：把「关闭」按钮挪到抽屉**顶部的固定头部**（header 不参与
  滚动，内容区单独 `overflow-y: auto`）。这样聚焦它时容器天然停在开头，
  一举两得：滚动位置正确 + 关闭入口更符合抽屉惯例。备选方案是
  `focus({ preventScroll: true })`，但那只是压掉症状——焦点仍在视野外的
  底部，键盘用户会迷失，不如调整布局根治。
  - 排版问题的根因是**双重内边距**：外层抽屉 `padding: 16px` + 内层
    SettingsView 又 `padding: 24px`，320px 宽的抽屉两边被吃掉 80px。
    修法是"内边距只归一个人管"——外层统一提供，内层组件不带 padding。
  - 中英文不对齐的根因是每行 label 宽度不一（inline-flex 各排各的）。
    改用 CSS Grid 两列（`grid-template-columns: max-content 1fr`），
    变量名列自动取最长项宽度，说明文字整齐成列。`display: contents`
    让 `<div>` 包裹层"隐身"，其子元素直接参与外层 grid 布局。

- 踩了什么坑：图谱页想让右侧详情栏与页头顶部对齐，flex 两行结构
  （header 行 + workspace 行）做不到——详情栏被困在第二行。改成
  grid 并让详情栏 `grid-row: 1 / 3` 跨两行才实现"贴顶通栏"。

## 2026-07-03 全局一致性收敛：语义尺寸 token + 统一断点 + 组件归一

- 做了什么：一轮全局 UI 审计后做三类收敛——① 新增语义尺寸 token
  （`--size-topbar/nav/sidebar`）替换散落的 `48px`/`240px`/`320px` 和
  `calc(--space-8 * 5)` 这类"拿间距凑宽度"的写法；② 响应式断点统一为
  `960px`（此前 Workbench/Library/ConversationSidebar 用 860、Graph 用
  960，两套并存）；③ TopBar 设置按钮、设置抽屉关闭按钮改用共享
  `Button`，工作台对话区/输入区外观 `composes` 自共享 `Card`；顺带让
  引用面板空态时收缩（`flex: 0 0 auto`），高度让给 AgentRoom。

- 这是什么：**语义 token** 是设计系统里"给尺寸起名字"的做法——
  `--size-sidebar: 320px` 表达的是"侧栏就该这么宽"这个决策，而不是
  一个碰巧等于 320 的数。`composes` 是 CSS Modules 的组合机制，让一个
  class 继承另一个文件里的 class，等于"样式层面的组件复用"。

- 为什么需要：同一个宽度在四个文件里各写一遍（还有用 `--space-8 * 5`
  乘出来的），改一处漏三处；两套断点意味着窗口宽 860~960px 之间切
  Tab 时布局会跳变；手写按钮样式和共享 Button 各长各的，日后主题
  调整必然漂移。

- 为什么这么做：token 放 `tokens.css` 是因为它就是"全局设计决策"的
  唯一归属地；断点选 960 而不是 860，是因为 Graph 页三栏内容最挤，
  它的临界值才是全局瓶颈。备选方案是引入容器查询（container query）
  按容器宽度自适应，但项目只有一个主布局，媒体查询够用，不加复杂度。

- 踩了什么坑：给共享 Button 传 `ref` 做焦点管理时，发现它没透传
  ref——React 19 里函数组件可以直接把 `ref` 声明成普通 prop
  （不再需要 `forwardRef`），在 `ButtonProps` 里加一行
  `ref?: Ref<HTMLButtonElement>` 即可，`{...rest}` 自然带过去。


## 2026-07-03 文档卡片改 Grid：auto-fill 让单张卡片不再拉满全宽

- 做了什么：文档库卡片列表从 flex wrap 改为 CSS Grid
  （`repeat(auto-fill, minmax(280px, 1fr))`），文档少时
  卡片保持合理宽度，不再横向拉伸占满整行。

- 这是什么：`auto-fill` 是 Grid 的"自动填轨道"关键字——按容器宽度
  能塞几条 ≥280px 的列就生成几条，**哪怕没内容也保留空轨道**。
  与它一字之差的 `auto-fit` 会把空轨道折叠掉，剩下的列平分全宽——
  那正是"只有一张卡就拉满"的老毛病，所以这里必须用 `auto-fill`。

- 为什么需要：旧写法 `flex: 1 1 <basis>` 的 `flex-grow: 1` 天生会
  吃掉整行剩余空间，单卡片被拉成横幅，视觉重心失衡；且 flex wrap
  的最后一行永远无法与上面几行对齐成整齐网格。

- 为什么这么做：窄屏单列回退用项目统一的 960px 媒体查询显式写
  `grid-template-columns: 1fr`，而不是靠 `minmax()` 里嵌套
  `min(280px, 100%)` 兜底——嵌套 min() 在部分旧引擎里会让整条
  `grid-template-columns` 声明被丢弃，显式断点更稳。另外容器是
  滚动区，要加 `align-content: start` 防止行在纵向剩余空间里被拉高。

- 踩了什么坑：第一版用了 `minmax(min(280px, 100%), 1fr)`，实测页面
  布局彻底错乱后回退重做，改成上面的"平铺写法 + 显式断点"。


## 2026-07-03 入库进度细化到逐 chunk + 删除 AgentRoom 死道具动画

- 做了什么：文档库进度提示改为中文阶段标签（stageLabels）+ 逐 chunk 进度
  message（后端每处理一个 chunk 发一条「正在从分块 3/15 中抽取实体与关系…」）；
  同时删除 AgentRoom 里入库/删除相关的道具动画（flydoc/paper/tag/cabglow/
  shredin/shredout）及其 CSS。

- 这是什么：前者是"长任务进度反馈"——SSE 事件的 message 字段本来就会被
  LibraryView 头部渲染（`lastMessage`），后端发得更密，前端不用改数据流就能
  持续看到活跃进度。后者是一次"死代码动画"清理：AgentRoom 只在工作台
  （问答 Run）挂载，文档处理的 uploading/parsing/extracting/indexing/deleting/
  rebuilding 事件只在文档库订阅、从不流到 AgentRoom——这些道具动画在真实
  运行中永远不会被触发。

- 为什么需要：extracting 阶段逐 chunk 调 LLM 动辄数分钟，之前整个阶段只有
  一条事件，前端停在同一句提示上呈现"卡死"错觉（正是上一条 DEVLOG 误诊
  SSE 丢事件的根源）。逐 chunk 事件让用户看到持续推进。死道具方面，项目
  红线是"像素动画必须来自真实 RunEvent"——只能被伪造 stage 触发的动画本身
  就违反红线，删除比保留更符合约定。

- 为什么这么做：进度粒度选"每 chunk 一条事件"而不是百分比——chunk 数就是
  天然的进度分母，无需前端进度条组件，一行文字即达意。保留 linking/searching
  两个道具（问答 Agent 真实会发这些 stage）；stage 到中文标签的映射放
  LibraryView 本地（sceneMap 是 AgentRoom 专属配置，不跨组件复用）。

- 踩了什么坑：无（后端跨线程 emit 沿用 run_chat 的 call_soon_threadsafe
  模式，见 backend/DEVLOG.md 同日记录）。


## 2026-07-03 F1 回答区 Markdown 化 + 引用角标内联芯片

- 做了什么：ChatThread 回答正文从纯文本插值改为 react-markdown + remark-gfm
  渲染；正文里的 `[n]` 角标预处理成 `[[n]](#cite-n)` 链接语法，覆写 markdown 的
  `a` 组件把 `#cite-` 前缀渲染成可点内联引用芯片（点击复用原有 CitationPanel
  高亮+滚动逻辑），越界号自然降级为纯文本；末尾按钮排改为「本回答引用：[1][2]…」
  汇总行，与正文角标复用同一芯片；配套 CSS 给 markdown 产物排版、用户气泡
  `pre-wrap`、代码块/表格 `overflow-x: auto`。

- 这是什么：react-markdown 是把 Markdown 字符串安全渲染成 React 元素的库
  （不启用 raw HTML，天然免 XSS）；remark-gfm 补上表格/删除线/任务列表等
  GitHub 风格扩展。「组件覆写」指用 `components={{ a: ... }}` 拦截某类节点自定义
  渲染——这里把引用角标从"纯文本"升级成"随句可点的芯片"。

- 为什么需要：回答是产品门面，之前 `.answerText` 无 `white-space`、正文纯插值，
  换行被折叠、列表/粗体/表格原样显示，文字挤成一团；角标两套并存（正文纯文本
  `[n]` + 末尾按钮）位置对不上。一行 CSS 只能救换行，救不了列表与结构。

- 为什么这么做：角标走「正则预处理 + a 覆写」而非自写 Markdown AST 插件——
  用 Markdown 原生链接语法承载角标，改动最小且天然继承解析器的括号处理；
  芯片抽成 ChatThread 内的局部组件，正文与汇总行复用一处造型/回调，不新建文件。
  用 micromark 实测 `[[1]](#cite-1)` 稳定解析为 `<a href="#cite-1">[1]</a>`，
  越界 `[999]` 也成链接、由覆写降级为纯文本，确认括号语义可靠后才落地。
  历史会话回灌（toChatMessages 已构造 answer 对象）自动走同一渲染路径，无需另改。

- 踩了什么坑：react-markdown v10 移除了组件自身的 `className` 属性，需外层包
  `<div className={styles.answerText}>` 承载排版样式；表格横向滚动用
  `display:block; width:max-content; max-width:100%; overflow-x:auto` 的
  GitHub 惯用写法，直接给 `<table>` 加 overflow 不生效。


## 2026-07-03 F2 图谱展示分级降噪（fcose + 度数分档 + 隐藏孤立点）

- 做了什么：GraphView 布局从内置 cose 换成 cytoscape-fcose；节点尺寸/颜色按
  度数分 3 档（+孤立档）——孤立灰小、高度数深大；新增「隐藏孤立节点」开关默认开
  （滤掉度数 0 的点及其悬挂边）；右侧实体列表改按度数降序、每项带类型 Chip 与
  度数徽标。度数来源写成 `nodeDegree()` 单函数：后端 degree 字段优先、缺省用
  edges 本地计数兜底。

- 这是什么：fcose 是 Cytoscape 的力导向布局插件（f = fast），大图上节点铺展与
  聚类质量明显优于内置 cose。「度数」= 一个实体在图里连了几条边，是最朴素的
  重要性信号：连得多的是核心概念，连 0 条的往往是抽取噪声。

- 为什么需要：后端列表按名字排序、画布全量平铺，核心节点与孤立噪声视觉权重
  相同，就是「机械粗糙」观感的展示层成因。用度数给节点分级 + 默认藏掉孤立点，
  能立刻把核心实体顶出来、把噪声压下去（噪声本身由后端 B1-B6 另线修抽取质量）。

- 为什么这么做：度数分「离散档位」而非连续插值——插值在小图上层次反而糊，
  3 档（浅→深、小→大）对比更利落，符合规格「不做连续插值」。degree 用
  `node.degree ?? edges 计数` 兜底：后端 B4 字段一旦到位，同一函数自动改用真值，
  无需二次改代码（这就是规格要求的「一处切换点」）。隐藏孤立时同时滤掉悬挂边
  （要求两端都可见），避免出现连不到点的孤边。实体列表始终含全部节点（含孤立），
  保证键盘可达路径不因画布隐藏而丢失，孤立点自然沉到列表末尾。

- 踩了什么坑：cytoscape-fcose 无官方 TS 类型，加 `src/cytoscape-fcose.d.ts`
  兜底 `declare module`；fcose 的 layout 选项（nodeSeparation 等）不在 cytoscape
  内置 LayoutOptions 联合类型里，用 `as unknown as cytoscape.LayoutOptions` 收口。
  注：度数分档/隐藏开关的最终视觉验收需连真实样本图数据肉眼过一遍（构建层已通过）。


## 2026-07-03 F3 AgentRoom 生命感（行为队列状态机）+ 修死掉的演出层

- 做了什么：把小人从「stage → 单一落点」升级为「stage → 一段行为剧本」的**行为队列
  状态机**。行为 = {目标工位 x, 微动作, 停留时长}：先走到 x（rAF 插值），到位后把微动作
  写到 canvas 的 `data-action` 上停留，再取下一个；队列空则续排——工作 stage 循环剧本
  （searching：档案柜翻找→抱文件走回桌→翻阅→循环；writing：打字+偶尔挠头/伸懒腰；
  linking：连线台比划；checking：桌前翻页），真实 idle 加权随机（喝咖啡/踱步/发呆/
  打瞌睡，间隔 8~20s）。新增随身道具：手持文件、zzz 气泡。顺手修了演出层的死选择器 bug，
  并给画布加"夜间小剧场"纵深光影。配套：linking 文案「拉关系」→「扩展图谱线索」；
  死 stage 就近标注"仅预览可达"；StyleGallery 改静态首帧预览；前端说明.md §8 同步。

- 这是什么：行为队列状态机 = 用一个队列描述"接下来依次做什么"，配 rAF 逐帧插值驱动
  位置、`data-action` 属性驱动姿态。`data-action` 是写在 DOM 上的普通属性，CSS 用
  `[data-action=type] .ar-dude` 这类**属性选择器**据它切换动画，不进 React 渲染（60fps
  不触发 re-render）。

- 为什么需要：小人可用动作只剩问答链路几个静态站位，"生命感"稀薄。更关键——排查时
  发现 `roomScenes.css` 的演出规则写成全局裸类名 `.canvas`/`.dude`，而元素挂的是 CSS
  Module 的哈希类名（`_canvas_xxx`/`_dude_xxx`），**两套对不上、永远命不中**：linking
  连线、searching 放大镜、error 红光+抖动其实**从来没显示过**（是死代码）。要做"生命感"
  绕不开先把这层选择器机制修对。

- 为什么这么做：① 选择器改「`[data-action]`/`[data-stage]` 属性选择 + 稳定全局类
  （`.ar-dude`/`.p-doc`…）」命中——属性选择器不依赖元素类名，天然命中哈希元素的祖先。
  ② 小人姿态原由 module 里 `[data-busy=1] .dude`（(0,3,0)）驱动，会盖过我的
  `[data-action] .ar-dude`（(0,2,0)）——干脆**退休 busy 摆动**，让 data-action 统一驱动
  小人所有姿态，消除层叠打架。③ 位置初值改由 hook 写 inline（去掉 JSX 硬编码 left），
  避免 stage 变化 re-render 把 left 重置；module 里留 `left:16%` 作挂载前占位防闪。
  ④ 中断即转沿用：stage 一变即 effect cleanup 丢当前队列、以真实当前位置为起点重排剧本。
  ⑤ 红线守住：stage 只来自真实 RunEvent，data-action 只是 stage 内部表现层编排；
  瞌睡/闲逛只在真实 idle；reduced-motion 时状态机静立仅呼吸、不排剧本、不走动。

- 踩了什么坑：核心坑就是上面那个"全局裸类名命不中哈希元素"的死选择器——只有连真实后端
  跑起来才看得出没显示，构建/类型都不报错，极隐蔽。教训：CSS Module 项目里，**全局 CSS
  文件不能用裸类名选 module 元素**，只能靠属性选择 + 显式挂的全局类。
  另：视觉层（姿态幅度、道具像素位置、光影）需在浏览器里肉眼逐项调，本次只保证构建绿 +
  StyleGallery 可静态预览全 12 状态首帧，精细视觉验收交人工过一遍。
