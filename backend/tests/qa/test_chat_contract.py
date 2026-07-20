"""Service-free contract tests for POST /api/chat conversation handling."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.conversations import Conversation
from app.runs import RunStore


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _HTTPException(Exception):
    def __init__(self, *, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class _Router:
    def __init__(self, **kwargs):
        pass

    def post(self, *args, **kwargs):
        return lambda function: function

    def get(self, *args, **kwargs):
        return lambda function: function


class _BackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, function, *args):
        self.tasks.append((function, args))


def _load_chat_module(monkeypatch):
    """Load the route with a tiny FastAPI facade; the test exercises only route logic."""
    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.APIRouter = _Router
    fake_fastapi.BackgroundTasks = _BackgroundTasks
    fake_fastapi.HTTPException = _HTTPException
    fake_fastapi.Request = object
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    path = Path(__file__).parents[2] / "app" / "routers" / "chat.py"
    spec = importlib.util.spec_from_file_location("_chat_contract_route", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _request():
    state = SimpleNamespace(neo4j=object(), runs=RunStore())
    return SimpleNamespace(app=SimpleNamespace(state=state))


@pytest.mark.anyio
async def test_unknown_supplied_conversation_returns_404_before_run_creation(monkeypatch):
    chat_mod = _load_chat_module(monkeypatch)
    monkeypatch.setattr(chat_mod, "get_conversation", lambda driver, cid: None)
    request = _request()
    background = _BackgroundTasks()

    with pytest.raises(_HTTPException) as exc_info:
        await chat_mod.chat(
            request,
            background,
            chat_mod.ChatRequest(question="follow up", conversation_id="missing"),
        )

    assert exc_info.value.status_code == 404
    assert request.app.state.runs._runs == {}
    assert background.tasks == []


@pytest.mark.anyio
async def test_existing_conversation_keeps_chat_response_contract(monkeypatch):
    chat_mod = _load_chat_module(monkeypatch)
    conversation = Conversation(conversation_id="conv-1", title="existing", message_count=1)
    monkeypatch.setattr(
        chat_mod, "get_conversation", lambda driver, cid: conversation
    )
    request = _request()
    background = _BackgroundTasks()

    response = await chat_mod.chat(
        request,
        background,
        chat_mod.ChatRequest(question="follow up", conversation_id="conv-1"),
    )

    assert set(response) == {"runId", "conversationId"}
    assert response["conversationId"] == "conv-1"
    assert len(request.app.state.runs._runs) == 1
    assert len(background.tasks) == 1
