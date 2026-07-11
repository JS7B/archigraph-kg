# 开发学习记录（基础设施 / 全局工作流）

> 本文件记录跨板块、基础设施、全局工作流相关的学习笔记。板块专属记录见各自目录下的 `DEVLOG.md`。
> 记录格式与写作要求见 `CLAUDE.md` / `AGENTS.md` 的「学习记录约定」。

---

## 2026-06-17 用 Git + GitHub 管理项目，并理清两种「身份」

- **做了什么**：把项目文件夹初始化成 git 仓库（`git init`），写好 `.gitignore`，做第一个提交，再用 `gh` CLI 登录 GitHub 后创建公开远程仓库并推送。
- **这是什么**：
  - Git 是「本地」的版本控制工具，记录每次改动的快照（commit）。GitHub 是把仓库放到云端的托管平台，两者是分开的。
  - commit 的署名（`user.name` / `user.email`）只是一段**纯文本标签**，git 不验证真假。
  - GitHub 认证（`gh auth login` 拿到的 token）才决定「你有没有权限把代码推上去」。
- **为什么需要**：版本控制让每一步可回溯、可对比、出错能回滚；推到 GitHub 则是为了备份、公开展示（写进简历）和将来多分支协作。
- **为什么这么做**：
  - 用 `gh` CLI 登录，是因为它会自动配好 git 的凭据助手，以后 `git push` 免密，比手动管理 token/SSH 省心。
  - 提交邮箱用 GitHub 账号**已验证**的邮箱（`lianzh1688@163.com`），这样 commit 才会正确归属到头像和贡献墙——GitHub 是靠 commit 里的邮箱来「对账」找人的。
- **踩了什么坑**：第一个 commit 用的是旧身份，发现后用 `git commit --amend --reset-author` 改写。注意 amend 会改变 commit 的 hash（因为内容变了），未推送前这样做是安全的。

---

## 2026-06-17 理解 git worktree：为什么它适合「多窗口并行开发」

- **做了什么**：学习了 worktree 的概念，作为后续并行开发的工作流基础（尚未实际建分支）。
- **这是什么**：普通 git 一个文件夹同一时刻只能在一个分支上，切分支要先 `git stash` 收起未提交改动，很打断思路。worktree 允许同一个仓库的**多个分支同时存在于不同文件夹**，共用同一份提交历史（`.git`）。
- **为什么需要**：想同时推进多条互不依赖的功能（比如「前端」和「实体抽取」），又不想互相干扰、反复切分支。每个 worktree 配一个独立的终端窗口和 Claude Code 会话，上下文天然隔离、互不污染。
- **为什么这么做**：相比开多个仓库克隆，worktree 共享历史、磁盘更省、分支管理统一。
- **踩了什么坑（提前规避）**：worktree 只隔离「代码文件」，但这些是**共享或会冲突**的，要心里有数：
  - 端口（如后端 8000、前端 5173）：两个 worktree 同时起服务会冲突，需错开端口或同一时刻只起一个。
  - `.env`：被 gitignore 了，新建 worktree 不会自动带过去，要手动复制一份。
  - Neo4j 数据：所有 worktree 连的是同一个数据库，并行写会互相污染，需约定串行使用或起独立容器。
  - 依赖（venv / node_modules）：每个 worktree 是独立文件夹，依赖不共享，要各自安装。

---

## 2026-06-17 安装 WSL2 + Docker Desktop

- **做了什么**：先 `wsl --install` 装好 WSL2，重启后用 winget 装 Docker Desktop 并首次启动。
- **这是什么**：
  - Docker 是「容器」工具：把一个软件（比如 Neo4j）连同它的运行环境打包成镜像，在隔离的容器里运行，不用在本机手动装一堆依赖。
  - 在 Windows 上，Docker Desktop 跑在 **WSL2**（Windows 内置的轻量 Linux 子系统）之上，所以必须先有 WSL2。
- **为什么需要**：项目规划要求「Neo4j 用 Docker 本地部署」。这样别人 clone 仓库后，一条 `docker compose up` 就能得到和你一模一样的数据库环境——这就是「可复现」。手动装 Neo4j 则人人环境不同、容易出错。
- **为什么这么做**：用 winget（Windows 官方包管理器）安装，命令式、可重复、省去手动下载安装包。
- **踩了什么坑**：
  1. `wsl --install` 跑完没弹出 Ubuntu 窗口，一度以为失败。其实 WSL2 内核已装好，只是没装 Linux 发行版——而 Docker Desktop **自带**它专用的发行版，不需要额外装 Ubuntu，可直接进行。
  2. Docker Desktop 装完不会自动启动，且首次启动要手动接受服务协议、等托盘鲸鱼图标变绿（Engine running）才算就绪。

---

## 2026-06-17 用 docker compose 跑起 Neo4j

- **做了什么**：写了 `docker-compose.yml` 定义 Neo4j 服务，`cp .env.example .env` 填密码后 `docker compose up -d neo4j` 拉起容器，并用 `cypher-shell` 实测连接成功。
- **这是什么**：
  - `docker-compose.yml` 是一份「声明式」配置：写清楚要跑哪个镜像、开哪些端口、数据存哪、密码从哪来，然后一条命令照着拉起来。
  - Neo4j 是图数据库，用节点和关系存数据，本项目用它存知识图谱，还用它的 Vector Index 做向量检索。
- **为什么需要**：把启动细节固化进文件，而不是记在脑子里或散落的命令里，任何人（包括未来的自己）都能一键复现同一套服务。
- **为什么这么做**：
  - 镜像选 `neo4j:5.26-community`：5.13+ 才支持原生向量索引，5.26 是长期支持版（LTS），稳定且满足需求。
  - 密码用 `${NEO4J_PASSWORD}` 从 `.env` 读取，**不硬编码**在 compose 里——符合「密钥零提交」硬规则。
  - 数据卷挂到 `./neo4j/data`，并在 `.gitignore` 里忽略它，确保数据库内容不会被误提交。
- **踩了什么坑**：
  1. healthcheck 里探活命令的密码，最初误写成 `$${NEO4J_PASSWORD}`（双 `$` 是转义给容器内 shell），但容器里没有这个变量。改成单 `$`，让 compose 在解析配置时就从 `.env` 插值进去。
  2. 第一次 `docker compose up` 拉镜像时连不上 Docker Hub（`registry-1.docker.io:443` 超时）——国内网络访问官方镜像仓库不稳定。切换网络后重试即成功。（长期方案：配置国内镜像加速器。）
  3. 容器刚 `Started` 时健康检查still是 `starting`，Neo4j 初始化要约 30 秒才转 `healthy`，需稍等再验证。

---

## 2026-07-11 建立 Codex 分支审计门禁

- **做了什么**：新增项目级 `Stop` / `SubagentStop` Hook 和可手动调用、不会改源码的分支审计脚本，覆盖改动范围、工作树、`git diff --check` 与板块验证命令，并补齐成功、异常失败和防循环测试。
- **这是什么**：Hook 是代理生命周期中的机械门禁，在 Codex 准备停止时执行确定性脚本；heartbeat 是定期查看并行工作线状态的只读观察者；主窗口则是阅读完整 diff、运行最终验证并决定是否合并的人。
- **为什么需要**：实现工人容易只验证自己刚改的局部，且多个 worktree 并行时问题可能较晚才暴露。三层审计让即时失败、跨窗口进度和最终合并分别有人负责，同时保持每条工作线的责任边界。
- **为什么这么做**：把路径选择与 Hook JSON 决策写成可单测的 Python 逻辑，并让 Hook 和主窗口复用同一个 CLI；运行异常统一 fail closed 为 block JSON，失败只请求继续一次，成功解析后的 `stop_hook_active=true` 优先放行，既能促使代理修正又不会无限循环。Hook 使用通用 `python3` 入口和 Windows `conda run` 覆盖，内部 pytest 则复用 `sys.executable`，路径始终从 git 根目录解析，不把个人绝对路径固化为跨机器方案。
- **踩了什么坑**：文件白名单不能像目录一样做前缀匹配，否则 `.bak` 和伪子路径会越权；git、JSON、npm 或执行器异常也不能直接冒泡成 exit 1，否则 Codex 收不到 continuation JSON。Windows 外层 `conda run` 若再嵌套一层 Conda，并转发 Unicode pytest 输出，还可能触发 GBK 编码失败，因此内部命令复用当前解释器，Hook stdout 统一为 ASCII JSON。Windows 的 PATH 还可能同时包含 `npm.ps1`、`npm.cmd` 和 extensionless npm：PowerShell 能解析前两者，但 Python 直接执行 `npm` 会命中不可执行的 POSIX launcher 并报 WinError 2，所以审计器在 Windows 明确选择 `npm.cmd`。`npm run build` 和 pytest 仍可能写 ignored 产物，而且分支可修改自身 Hook，所以它是受信任协作门禁，不是恶意分支安全边界。
