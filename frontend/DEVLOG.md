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
