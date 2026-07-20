"""Deterministic tests for atomic, idempotent conversation-turn persistence."""

from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.conversations import append_turn, get_messages
from app.conversations import store as store_mod
from app.qa.models import Citation


class _Record(dict):
    def data(self):
        return dict(self)


class _Result(list):
    def single(self):
        return self[0] if self else None


class _FakeTransaction:
    def __init__(self, state):
        self.state = state

    def run(self, query, **params):
        if query == store_mod._LOCK_CONVERSATION:
            conversation = self.state["conversations"].get(params["conversation_id"])
            if conversation is None:
                return _Result()
            conversation["message_count"] = conversation.get("message_count", 0)
            conversation["_turn_lock"] = conversation.get("_turn_lock", 0) + 1
            conversation["turn_counter"] = conversation.get(
                "turn_counter", conversation["message_count"]
            )
            return _Result(
                [_Record(turn_counter=conversation["turn_counter"])]
            )

        if query == store_mod._GET_TURN_BY_RUN:
            rows = [
                _Record(**message)
                for message in self.state["messages"].values()
                if message["conversation_id"] == params["conversation_id"]
                and message.get("run_id") == params["run_id"]
            ]
            return _Result(sorted(rows, key=lambda row: row["turn_index"]))

        if query == store_mod._CREATE_TURN:
            conversation = self.state["conversations"][params["conversation_id"]]
            rows = []
            for prefix in ("user", "agent"):
                message = {
                    "message_id": params[f"{prefix}_message_id"],
                    "conversation_id": params["conversation_id"],
                    "run_id": params["run_id"],
                    "turn_index": params[f"{prefix}_turn_index"],
                    "role": prefix,
                    "text": params[f"{prefix}_text"],
                    "citations": params[f"{prefix}_citations"],
                    "confidence": params[f"{prefix}_confidence"],
                    "embedding": params[f"{prefix}_embedding"],
                    "created_at": params["created_at"],
                }
                self.state["messages"][message["message_id"]] = message
                rows.append(_Record(**message))
            conversation["turn_counter"] = params["agent_turn_index"]
            conversation["message_count"] += 2
            return _Result(rows)

        raise AssertionError(f"Unexpected managed-transaction query: {query}")


class _FakeSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute_write(self, callback, *args, **kwargs):
        with self.driver.lock:
            working = copy.deepcopy(self.driver.state)
            result = callback(_FakeTransaction(working), *args, **kwargs)
            if self.driver.fail_before_commit:
                raise RuntimeError("injected commit failure")
            self.driver.state = working
            return result


class _FakeDriver:
    def __init__(self, *, conversation_exists=True, fail_before_commit=False):
        self.state = {
            "conversations": (
                {"conv-1": {"message_count": 0, "turn_counter": 0}}
                if conversation_exists
                else {}
            ),
            "messages": {},
        }
        self.fail_before_commit = fail_before_commit
        self.lock = threading.Lock()

    def session(self, *, database):
        assert database == "neo4j"
        return _FakeSession(self)

    def execute_query(self, query, **params):
        assert query == store_mod._GET_MESSAGES
        rows = [
            _Record(**message)
            for message in self.state["messages"].values()
            if message["conversation_id"] == params["conversation_id"]
        ]
        return sorted(rows, key=lambda row: row["turn_index"]), None, None


def _append(driver, run_id="run-1", *, user_text="question", agent_text="answer"):
    return append_turn(
        driver,
        "conv-1",
        run_id=run_id,
        user_text=user_text,
        agent_text=agent_text,
        user_embedding=[1.0, 0.0],
        agent_embedding=[0.0, 1.0],
        citations=[
            Citation(
                index=1,
                chunk_id="chunk-1",
                document_id="doc-1",
                location="section 1",
                snippet="evidence",
            )
        ],
        confidence="high",
    )


def test_atomic_happy_path_persists_complete_adjacent_pair():
    driver = _FakeDriver()

    user, agent = _append(driver)

    assert (user.turn_index, agent.turn_index) == (1, 2)
    assert (user.role, agent.role) == ("user", "agent")
    assert user.citations == []
    assert agent.citations[0].chunk_id == "chunk-1"
    assert agent.confidence == "high"
    assert driver.state["conversations"]["conv-1"] == {
        "_turn_lock": 1,
        "message_count": 2,
        "turn_counter": 2,
    }
    stored = sorted(driver.state["messages"].values(), key=lambda row: row["turn_index"])
    assert [row["embedding"] for row in stored] == [[1.0, 0.0], [0.0, 1.0]]


def test_failure_before_commit_leaves_no_partial_turn():
    driver = _FakeDriver(fail_before_commit=True)

    with pytest.raises(RuntimeError, match="commit failure"):
        _append(driver)

    assert driver.state["messages"] == {}
    assert driver.state["conversations"]["conv-1"]["message_count"] == 0


def test_retry_same_run_returns_original_pair_without_overwrite():
    driver = _FakeDriver()
    first = _append(driver)
    second = _append(driver, user_text="different", agent_text="different")

    assert [message.message_id for message in second] == [
        message.message_id for message in first
    ]
    assert [message.text for message in second] == ["question", "answer"]
    assert len(driver.state["messages"]) == 2
    assert driver.state["conversations"]["conv-1"]["message_count"] == 2


def test_concurrent_distinct_runs_receive_unique_ordered_pairs():
    driver = _FakeDriver()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda run_id: _append(driver, run_id), ["run-a", "run-b"]))

    pairs = sorted((user.turn_index, agent.turn_index) for user, agent in results)
    assert pairs == [(1, 2), (3, 4)]
    assert len({message.message_id for pair in results for message in pair}) == 4
    assert driver.state["conversations"]["conv-1"]["message_count"] == 4


def test_old_format_messages_remain_readable_and_ordered():
    driver = _FakeDriver()
    driver.state["messages"] = {
        "legacy-2": {
            "message_id": "legacy-2",
            "conversation_id": "conv-1",
            "turn_index": 2,
            "role": "agent",
            "text": "old answer",
            "citations": None,
            "confidence": "low",
            "created_at": 2,
        },
        "legacy-1": {
            "message_id": "legacy-1",
            "conversation_id": "conv-1",
            "turn_index": 1,
            "role": "user",
            "text": "old question",
            "citations": None,
            "confidence": None,
            "created_at": 1,
        },
    }

    messages = get_messages(driver, "conv-1")

    assert [message.message_id for message in messages] == ["legacy-1", "legacy-2"]
    assert [message.text for message in messages] == ["old question", "old answer"]


def test_missing_conversation_rejected_before_any_message_write():
    driver = _FakeDriver(conversation_exists=False)

    with pytest.raises(store_mod.ConversationNotFound):
        _append(driver)

    assert driver.state["messages"] == {}
