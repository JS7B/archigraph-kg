"""RunStore 单元测试：create/append/subscribe/终态关闭/历史投递。

纯 Python 逻辑，不连 Neo4j、不依赖 LLM。subscribe 用 anyio 跑事件循环。
"""

import pytest

from app.runs import Run, RunEvent, RunKind, RunStatus, RunStore, Stage


def _evt(stage: Stage, status: RunStatus = RunStatus.RUNNING, **kw) -> RunEvent:
    return RunEvent(stage=stage, status=status, **kw)


def test_create_run_assigns_id_and_running_status():
    s = RunStore()
    r = s.create_run(RunKind.CHAT)
    assert r.id
    assert r.status == RunStatus.RUNNING
    assert r.is_terminal is False
    assert r.current_stage == Stage.IDLE  # 无事件时 idle
    assert s.get_run(r.id) is r
    assert s.get_run("nope") is None


def test_append_event_records_and_updates_status():
    s = RunStore()
    r = s.create_run(RunKind.INGEST)
    s.append_event(r.id, _evt(Stage.PARSING))
    s.append_event(r.id, _evt(Stage.INDEXING))
    assert len(r.events) == 2
    assert r.current_stage == Stage.INDEXING
    assert r.status == RunStatus.RUNNING


def test_append_event_assigns_incrementing_seq():
    """seq 由 append_event 统一赋值（Run 内 1 起递增），前端断线重连按它去重。"""
    s = RunStore()
    r = s.create_run(RunKind.INGEST)
    s.append_event(r.id, _evt(Stage.PARSING))
    s.append_event(r.id, _evt(Stage.INDEXING))
    s.append_event(r.id, _evt(Stage.IDLE, RunStatus.SUCCEEDED))
    assert [e.seq for e in r.events] == [1, 2, 3]
    # 不同 Run 各自独立计数
    r2 = s.create_run(RunKind.CHAT)
    s.append_event(r2.id, _evt(Stage.SEARCHING))
    assert r2.events[0].seq == 1


def test_terminal_event_sets_status():
    s = RunStore()
    r = s.create_run(RunKind.INGEST)
    s.append_event(r.id, _evt(Stage.PARSING))
    s.append_event(r.id, _evt(Stage.IDLE, RunStatus.SUCCEEDED))
    assert r.status == RunStatus.SUCCEEDED
    assert r.is_terminal is True
    # 失败
    r2 = s.create_run(RunKind.CHAT)
    s.append_event(r2.id, _evt(Stage.ERROR, RunStatus.FAILED, message="boom"))
    assert r2.status == RunStatus.FAILED
    assert r2.events[-1].message == "boom"


def test_append_to_missing_run_raises():
    s = RunStore()
    with pytest.raises(KeyError):
        s.append_event("missing", _evt(Stage.IDLE))


@pytest.mark.anyio
async def test_subscribe_receives_new_events_after_subscription():
    s = RunStore()
    r = s.create_run(RunKind.INGEST)
    s.append_event(r.id, _evt(Stage.UPLOADING))  # 历史事件
    q = await s.subscribe(r.id)
    # subscribe 后的新事件应入队
    s.append_event(r.id, _evt(Stage.PARSING))
    s.append_event(r.id, _evt(Stage.IDLE, RunStatus.SUCCEEDED))
    received = []
    while not q.empty():
        received.append(await q.get())
    stages = [e.stage for e in received]
    assert Stage.UPLOADING in stages  # 历史事件也被投递（不漏）
    assert Stage.PARSING in stages
    assert received[-1].status == RunStatus.SUCCEEDED
    # 回放的历史事件保留原 seq（重连去重的前提）
    assert [e.seq for e in received] == [1, 2, 3]
    s.unsubscribe(r.id, q)


@pytest.mark.anyio
async def test_subscribe_to_missing_run_raises():
    s = RunStore()
    with pytest.raises(KeyError):
        await s.subscribe("nope")


def test_run_model_alias_camel_case():
    """Run 的 id/created_at 有 alias，model_dump(by_alias=True) 输出 camelCase。"""
    r = Run(kind=RunKind.CHAT)
    dumped = r.model_dump(by_alias=True)
    assert "runId" in dumped
    assert "createdAt" in dumped
