# 分支审计工作流

本项目用三层审计把“机械检查”“周期观察”和“合并决策”分开：Codex Hook 在代理准备停止时运行确定性门禁，heartbeat 只读观察并行工作线，主窗口最终检查完整 diff 并决定是否合并。三者互相补充，不能互相替代。

## Hook 启用与信任

项目级配置位于 `.codex/hooks.json`，同时监听 `Stop` 和 `SubagentStop`。Codex 只会在项目 `.codex/` 配置层受信任、且具体 Hook 定义经过审阅后运行它；配置内容变化后，原有信任不会自动沿用。请在 Codex 中执行 `/hooks`，核对来源、命令和脚本内容后再信任。

新建或修改 Hook 后，当前会话不一定热加载新配置。若 `/hooks` 中尚未显示本次定义，应在新会话中重新检查；在此之前必须手动调用同一个审计脚本，不能把“文件已经存在”当作运行证据。Hook 的当前配置格式和信任机制见 [Codex Hooks 官方说明](https://learn.chatgpt.com/codex/hooks)。

Hook 的通用入口使用 `python3`，Windows 则通过 `commandWindows` 使用项目约定的 `conda run -n myself python`。两者都先执行 `git rev-parse --show-toplevel` 再定位脚本，因此即使 Codex 从仓库子目录启动，也不会依赖当前工作目录。

## 审计内容

审计脚本只审计 `feat/*`；`main` 和其他分支直接放行，因为合并权属于主窗口。功能分支会执行以下只读检查：

- 收集 `main...HEAD`、未暂存和已暂存的改动路径，按首次出现顺序去重；
- 检查工作树是否干净，并分别运行提交、未暂存和已暂存差异的 `git diff --check`；
- 对三条固定工作线检查文件范围，防止工人越界修改；
- `frontend/` 改动选择 lint、typecheck、Vitest 和构建，`evals/`/评估文档改动选择评估单测，Hook/审计测试改动选择审计单测；
- Python 单测命令使用启动 Hook 的 `sys.executable -m pytest`，复用已经选定的环境，不在 Windows `commandWindows` 外层之内再次嵌套 `conda run`；
- 非前端质量分支缺少某个 npm script 时明确记录为跳过，避免无关分支因尚未合并的前端脚本失败。

脚本不会读取或输出 `.env`，不会运行真实 LLM 评估，也不会写文件、提交、合并或推送。首次失败输出 `{"decision":"block","reason":"..."}`，提示 Codex 继续修正；JSON 保持 ASCII 安全，非 ASCII 原因会转义后写入 stdout，并可由 JSON 解析恢复原文。若事件已带 `stop_hook_active=true`，脚本返回 `{"continue":true}`，避免同一个停止事件无限循环。

## 手动调用与故障排查

在仓库根目录执行项目约定入口：

```powershell
conda run -n myself python .codex/hooks/audit_gate.py --repo <worktree>
```

macOS/Linux 或未使用 Conda 的环境可使用通用入口：

```bash
python3 .codex/hooks/audit_gate.py --repo <worktree>
```

成功时 stdout 是 `{"continue": true}`；失败时 stdout 是带原因的 `decision: block` JSON。手动调用适用于当前会话尚未加载 Hook，或主窗口终审某个物理 worktree。它只证明确定性门禁通过，不能替代主窗口检查 `main...branch` 完整 diff、提交范围、依赖锁文件、DEVLOG、密钥与运行数据边界。

Windows override 只用 `conda run` 启动一次 Hook；脚本内部的 pytest 复用 `sys.executable`，不会再套一层 Conda。失败原因即使包含 Unicode，也会作为 ASCII 转义的 JSON 输出，从而避开 Conda 转发 Unicode pytest 文本时可能出现的 GBK 编码错误。手动排障时也可先 `conda activate myself`，再用当前环境 PATH 中的 `python` 运行同一脚本；不要把某台机器的 Python 绝对路径写成仓库唯一入口。

## Heartbeat 与收尾

10 分钟 heartbeat 只读查看 `git worktree list`、各分支相对 `main` 的 diff、最新提交和失败测试迹象；它不修改文件、不提交、不合并、不推送。三条工作线完成合并或对应 worktree 被回收后，必须停止 heartbeat，避免对已结束批次继续巡检。

最终合并仍由主窗口完成：先读完整 diff，再运行板块验证，检查依赖、锁文件、DEVLOG 和数据边界；发现问题退回原工人修正，全部通过后才合并。
