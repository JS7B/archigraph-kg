"""extract_chunk：正常解析、首次失败后重试成功、持续失败抛 ExtractionError。"""

import pytest

from app.extraction import llm_extract
from app.extraction.errors import ExtractionError

_GOOD = '{"entities": [{"name": "A", "type": "项目"}], "relations": []}'


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(llm_extract.time, "sleep", lambda _s: None)


def test_parses_valid_response(monkeypatch):
    monkeypatch.setattr(llm_extract.llm, "chat", lambda m, **k: _GOOD)
    result = llm_extract.extract_chunk("d#0", "文本")
    assert result.entities[0].name == "A"


def test_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_chat(messages, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "不是 json"
        return _GOOD

    monkeypatch.setattr(llm_extract.llm, "chat", fake_chat)
    result = llm_extract.extract_chunk("d#0", "文本", max_attempts=3)
    assert result.entities[0].name == "A"
    assert calls["n"] == 2


def test_raises_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr(llm_extract.llm, "chat", lambda m, **k: "坏数据")
    with pytest.raises(ExtractionError) as exc_info:
        llm_extract.extract_chunk("d#3", "文本", max_attempts=2)
    assert exc_info.value.chunk_id == "d#3"
    assert exc_info.value.reason
