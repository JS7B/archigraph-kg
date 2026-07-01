# 交接清单 · 入库终态事件丢失（SSE bug）· 前后端联合排查

> 大脑已做深度诊断，把范围缩到最小。工人按此排查可省去大量定位时间。
> 后端 feat/backend + 前端 feat/frontend 联合排查（根因跨前后端，未最终定位）。

## 一、现象

- **入库完成后，前端文档列表不自动刷新**，必须手动刷新页面才看到新文档。
- 删除流程同理（终态事件不到前端）。
- 但后端实际入库是成功的（Neo4j 里有数据），纯粹是**前端收不到终态事件**。

## 二、大脑已查清的诊断（关键，省去重复排查）

### 2.1 后端 SSE 推送本身是正常的

用 Python requests 流式模拟 EventSource，能收到完整 5 条事件，**含终态**：
```
uploading/running → parsing/running → extracting/running → indexing/running → idle/succeeded
```
（见大脑测试日志，requests.iter_lines 能读到 succeeded）。所以**后端发了终态**。

### 2.2 前端 LibraryView 的终态处理逻辑是正确的

LibraryView.tsx:84-96 的 useEffect 监听 events，收到 succeeded 就 refresh()——**代码逻辑没问题**。

### 2.3 真实断点：浏览器 EventSource 收不到第 5 条（终态）事件

加 console.log 到 LibraryView 后，用户实测日志：
```
events.len= 4 last= indexing / running     ← 最后收到的永远是第4条（indexing）
终态useEffect触发, last.status= running     ← 永远是 running，从未变成 succeeded
```
**即：第 5 条 `idle/succeeded` 终态事件从未到达浏览器的 onmessage 回调。**

### 2.4 已排除的猜测

- ❌ 后端没发终态（已证伪：requests 能收到）
- ❌ LibraryView 没写终态处理（已证伪：代码在，且 useEffect 会触发，只是 status 一直是 running）
- ❌ 0.2s sleep 延迟关闭连接（大脑试过，**无效**——前端仍收不到，已回退）

### 2.5 高度怀疑方向（工人重点查）

**怀疑1：sse-starlette 的缓冲/关闭时序**
后端 runs.py:54-56 `yield 终态事件` 后立即 `break`，generator 结束触发连接关闭。怀疑 sse-starlette 在 generator 结束时**先关闭连接、再 flush 缓冲**，导致最后一条事件没真正发出去。requests 能收到可能是因为它阻塞同步读、时序不同；浏览器 EventSource 异步读，连接关太快导致丢失。
- 排查：查 sse-starlette 版本和已知 issue；试 `await asyncio.sleep` 加在 yield 前（不是后）；或用 StreamingResponse 替代 EventSourceResponse 对比。

**怀疑2：浏览器 EventSource 对 `event: message` + 立即关闭的处理**
sse.ts:42 `source.onmessage` 只处理无显式 event 类型或 `event: message` 的消息。后端发的是 `{"event":"message","data":...}`（runs.py:54）。检查：浏览器是否因为连接关闭（readyState 变化）而丢弃了已到达但未 dispatch 的 message 事件。
- 排查：在 sse.ts 的 `source.addEventListener('message', ...)` 加日志；或在 onerror 里主动查 `/api/runs/{id}/events` 历史补全（这是更稳健的兜底修法，见 §三）。

## 三、推荐修复方向（两个层面，择一或都做）

### 方案 A：前端兜底（推荐，最稳健）

前端收到 SSE `onerror` 或连接关闭时，**主动查一次 `/api/runs/{runId}/events` 历史接口**，补全可能丢失的终态事件。这样即使 SSE 流有问题，终态也能通过 HTTP 历史接口兜住。

改 `frontend/src/api/sse.ts` 的 `source.onerror`：
```ts
source.onerror = (err) => {
  source.close()
  // 兜底：SSE 可能丢失终态，查历史补全
  fetch(`${BASE_URL}/api/runs/${runId}/events`)
    .then(r => r.json())
    .then(events => {
      const last = events[events.length - 1]
      if (last && (last.status === 'succeeded' || last.status === 'failed')) {
        onEvent(last)  // 补投终态事件
      }
    })
  onError(err)
}
```
注意：onerror 在正常终态 close 后也会触发（sse.ts:76 已处理 readyState===CLOSED 直接 return），需区分"正常关闭"和"异常中断"——正常关闭（source.close() 后）readyState 是 CLOSED，此时不查历史；异常中断才查。

### 方案 B：后端调整 SSE 关闭时序

查 sse-starlette 文档/issue，确保 yield 终态后数据真正 flush 再关闭。可能需要：
- yield 后 `await asyncio.sleep(0.5)` 让缓冲 flush（大脑试过 0.2s 无效，可加到 1s 试，但不优雅）
- 或换用原生 StreamingResponse 自己控制关闭
- 或在终态后再发一条额外的 noop 事件（如 ping）确保前一条被冲刷出去

## 四、附带 bug：入库后图谱不刷新

GraphView 的实体关系在入库后不自动显示，需手动刷新。**大概率是本 bug 的连带后果**（终态没到 → refresh 没触发 → 图谱没刷）。
- 先修好 SSE 终态问题，再验证图谱是否自动刷新。
- 若仍不刷新：GraphView 当前只在 mount 时拉一次 `/api/graph/*`（视图常驻后不重拉），可能需要监听"文档库有新入库"事件来刷新图谱——这属于独立的前端改动。

## 五、验证

- [ ] 上传文档 → 不刷新页面 → 文档列表自动出现新文档（终态到达触发 refresh）
- [ ] 删除文档 → 终态到达 → 列表自动移除（无需手动刷新）
- [ ] 入库后图谱视图自动显示新实体（若仍不刷，按 §四 独立处理）
- [ ] 后端 pytest 不回归

## 六、交接

前后端可各自在自己的 worktree 排查（方案 A 改前端 sse.ts，方案 B 改后端 runs.py）。
建议**先试方案 A（前端兜底）**，它最稳健且只改前端。本地 commit 后通知大脑 review。
