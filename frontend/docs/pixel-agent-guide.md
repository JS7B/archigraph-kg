# 像素 Agent 动画指南

像素管理员是 graphrag-kg-agent 的吉祥物：一个戴眼镜的档案管理员，根据后端
运行状态做出 12 种拟物动作。本文是维护和扩展它的指南。

## 红线（不可破）

**动画状态必须来自真实 RunEvent。** 数据流是单向的：

    后端 RunEvent → useRunEvents 钩子 → currentStage → PixelAgent

`PixelAgent` 的 `devControls` 仅供开发预览（手动切 stage 看效果），
**禁止用它驱动生产状态**。生产中 stage 只能从真实事件派生。

## 文件结构

- `src/components/PixelAgent/PixelAgent.tsx` —— 分层小人结构（头/身/左右手/道具）。
- `src/components/PixelAgent/PixelAgent.module.css` —— 各图层定位与尺寸。
- `src/components/PixelAgent/animations.css` —— 每个 stage 的 @keyframes。
- `src/components/PixelAgent/stageMap.ts` —— stage → {label, animClass, scene} 映射。

## 12 个状态动作表

| stage | 动作 | 场景元素 |
|---|---|---|
| idle | 待命，呼吸浮动（眨眼等细节待补） | 安静的工作间 |
| uploading | 搬运文档进门 | 门口收件筐 |
| parsing | 蹲下拆文件包 | 拆包台 |
| extracting | 贴实体标签 | 标签贴纸 |
| linking | 拉关系线 | 连线板 |
| indexing | 归档进档案柜 | 档案柜抽屉 |
| searching | 翻找文件 | 文件堆 |
| checking | 放大镜校对引用 | 放大镜 |
| writing | 打字输出 | 打字机 |
| deleting | 塞进碎纸机 | 碎纸机 |
| rebuilding | 复印重排 | 复印机 |
| error | 看错误纸条挠头 | 红色纸条 |

## 当前完成度

`idle` 已做出可见的呼吸动画作为 CSS 分层方案样板。其余 11 个状态的
animClass 已就位，但动作是占位（轻微浮动）。

## 加 / 完善一个状态的步骤

1. 在 `stageMap.ts` 确认该 stage 的 `label` 与 `scene` 文案。
2. 在 `animations.css` 为它的 `animClass`（如 `.anim-writing`）写专属
   `@keyframes`，驱动 `PixelAgent.module.css` 里的图层（手臂摆动用
   `.armLeft/.armRight` 的 transform，道具进出场用 `.prop` 的 opacity/transform）。
3. `npm run dev`，用开发预览切到该 stage 检查效果。
4. 状态切换的平滑（最短停留、排队）在 useRunEvents 接入真实 SSE 时实现：
   只平滑/排队已发生的真实事件，绝不伪造未发生的事件。

## 后续升级方向

当前为 CSS 分层 + keyframes 方案（方案 B）。有余力可升级为逐帧
sprite sheet（方案 A），届时替换 `animations.css` 与图层渲染方式，
但 stageMap 与 useRunEvents 的接口保持不变。
