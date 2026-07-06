# 交接清单（前端工人 · feat/frontend）：AgentRoom 小基地升级

> 大脑 2026-07-06 签发。设计规格见
> `docs/superpowers/specs/2026-07-06-agentroom-base-upgrade-design.md`，
> 细化实施计划见
> `docs/superpowers/plans/2026-07-06-agentroom-base-upgrade.md`。

## 目标

把当前 `AgentRoom` 从“能工作但人物感偏弱的状态指示器”升级成一个更完整的
**像素小工程师基地**：

- 小人重画，人物感更明确；
- 咖啡角从站位升级成真实互动；
- `doze` 不再只靠 `zzz`，而是用五官也能读懂；
- 房间更像一个会工作的混合型小基地。

## 本批次只做前端

后端窗口 **本批次不用动**。不要改 `Stage`、`RunEvent`、SSE 契约，不要新增依赖。

只有当前端实施发现“必须新增 stage / 必须新增事件字段 / 必须重命名 stage”时，
再通知大脑决定是否派后端补充清单。

## 开工前两条实现提醒

1. `drink` 不是单纯样式问题。当前 idle 机制只返回单段 `Behavior`，要做成“取杯 -> 喝 -> 停顿”，需要同时小幅修改 `behaviors.ts` 和 `useAgentPosition.ts`，把 idle 也接到可消费的短剧本队列上。
2. 不要硬套计划里示意性的 `.coffee-station` / `.p-steam`。现状咖啡角和蒸汽节点在 `AgentRoom.module.css` 里走 CSS Module，前端实施时应先在 `AgentRoom.tsx` 补稳定类名或 `data-*` 属性，再让 `roomScenes.css` 用这些稳定钩子做“被取用感”。

## 要改的文件

- `frontend/src/components/AgentRoom/drawDude.ts`
- `frontend/src/components/AgentRoom/behaviors.ts`
- `frontend/src/components/AgentRoom/AgentRoom.tsx`
- `frontend/src/components/AgentRoom/AgentRoom.module.css`
- `frontend/src/components/AgentRoom/roomScenes.css`
- `frontend/src/components/AgentRoom/sceneMap.ts`
- `frontend/src/views/StyleGallery/StyleGallery.tsx`
- `frontend/src/views/StyleGallery/StyleGallery.module.css`
- `frontend/前端说明.md`
- `frontend/DEVLOG.md`

## 执行顺序

1. 先重画小人：眼镜、眼睛、嘴部可读性上来。
2. 再改 `drink`：做成“取杯-喝-停顿”。
3. 再改 `doze`：闭眼横线 + 圆口呼吸。
4. 最后升级房间层次和文档。

## 红线

- `stage` 仍然只来自真实 `RunEvent`。
- 不把 `AgentRoom` 改成 sprite sheet / canvas 重写。
- `prefers-reduced-motion` 不退化。
- 房间升级是“做精”，不是彻底换风格。

## 验收

- 第一眼更像小工程师，而不是抽象色块。
- `drink` 明显是和咖啡交互，不只是站在咖啡角。
- `doze` 不看 `zzz` 也能看懂。
- 房间更像 Agent 小基地，主工位、咖啡角、资料柜分工更清楚。
- `npm run typecheck` / `npm run build` 通过。

## 提交要求

- 按计划任务分段 commit，别攒一大坨。
- 完成后通知大脑按 commit / diff 复审。
- 不碰 `main`，不自行合并。
