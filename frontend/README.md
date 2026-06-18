# graphrag-kg-agent 前端

GraphRAG 工作台前端：React + Vite + TypeScript。

## 启动

    cd frontend
    cp .env.example .env   # 按需修改 VITE_API_BASE_URL
    npm install
    npm run dev

## 脚本

- `npm run dev` —— 开发服务器
- `npm run build` —— 生产构建
- `npm run preview` —— 预览生产构建
- `npm run typecheck` —— TypeScript 类型检查

## 当前状态

工程脚手架阶段：顶部导航 + 三视图（问答工作台 / 文档库 / 图谱）+ 设置页
均为占位实现；数据钩子与 API 客户端留接口、返回占位，未接业务后端。
像素管理员 idle 动作已可见，其余状态留占位。

## 结构

- `src/types/` —— 数据契约类型（前端需求版）
- `src/api/` —— fetch 封装（对接统一错误结构）
- `src/hooks/` —— useRunEvents（事件流钩子，预留 SSE）
- `src/views/` —— 三视图 + 设置
- `src/components/` —— TopBar / 工作台子组件 / PixelAgent
- `src/styles/` —— 设计 token 与全局样式
- `docs/pixel-agent-guide.md` —— 像素 Agent 动画维护指南

设计规格见 `../docs/superpowers/specs/2026-06-17-frontend-workbench-design.md`。
