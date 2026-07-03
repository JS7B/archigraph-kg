"""进程内 Run 注册表：存历史 + 支持 SSE 订阅。

不持久化：重启后 Run/Event 丢失。Run 是瞬态进度信号，前端刷新会重新查
Document 状态（落 Neo4j），丢失 Run 进度可接受。符合 CLAUDE.md「简单优先」。

订阅用 asyncio.Queue：每个订阅者一个队列，append_event 时向所有队列投递事件副本。
终态事件（status=succeeded/failed）后，is_terminal 让订阅者知道流该关闭。

TTL 清理：终态 Run 保留 _TTL_SECONDS（10 分钟）后由 create_run 顺带清理，避免长跑
内存泄漏。未终态的 Run 不清理（可能在执行中）。
"""

import asyncio
import time

from app.runs.models import Run, RunEvent, RunKind, RunStatus, Stage

# 终态 Run 的保留时长（秒）。超过则被 _gc 清理；个人项目单用户，10 分钟够前端重连。
_TTL_SECONDS = 600


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def create_run(self, kind: RunKind) -> Run:
        self._gc()  # 顺带清理过期终态 Run，防长跑内存泄漏
        run = Run(kind=kind)
        self._runs[run.id] = run
        self._subscribers[run.id] = []
        return run

    def _gc(self) -> None:
        """清理已终态且超过 TTL 的 Run。未终态的不动（可能仍在执行）。"""
        now = time.time() * 1000
        expired = [
            rid
            for rid, run in self._runs.items()
            if run.is_terminal and (now - run.created_at) > _TTL_SECONDS * 1000
        ]
        for rid in expired:
            self._runs.pop(rid, None)
            self._subscribers.pop(rid, None)

    def get_run(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def append_event(self, run_id: str, event: RunEvent) -> None:
        """记录事件到历史，并向所有订阅者投递副本。Run 终态即随事件更新。

        seq 在此统一赋值（Run 内 1 起递增）：前端断线重连时 subscribe 会回放
        全部历史，前端按 seq 去重即可安全消费重复投递。
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run 不存在: {run_id}")
        event.seq = len(run.events) + 1
        run.events.append(event)
        if event.status in (RunStatus.SUCCEEDED, RunStatus.FAILED):
            run.status = event.status
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)

    def events(self, run_id: str) -> list[RunEvent]:
        return list(self._runs[run_id].events) if run_id in self._runs else []

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        """订阅一个 Run 的新事件。调用方从 queue.get() 取事件，is_terminal 后退出。"""
        if run_id not in self._runs:
            raise KeyError(f"Run 不存在: {run_id}")
        queue: asyncio.Queue = asyncio.Queue()
        # 先投递历史事件，保证订阅者不漏掉 append 在 subscribe 之前的事件。
        for event in self._runs[run_id].events:
            queue.put_nowait(event)
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id, [])
        if queue in subs:
            subs.remove(queue)
