"""prompt 构造：含 json 字样、含 chunk 文本、system+user 两条。"""

from app.extraction.prompt import build_messages
from app.parsing.models import ExtractionPolicy


def test_messages_have_system_and_user():
    msgs = build_messages("一些文本")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


def test_messages_mention_json():
    # json_object 模式要求 prompt 出现 "json" 字样（大小写不敏感检查）
    msgs = build_messages("一些文本")
    combined = (msgs[0]["content"] + msgs[1]["content"]).lower()
    assert "json" in combined


def test_user_message_carries_chunk_text():
    msgs = build_messages("FastAPI 依赖 Pydantic")
    assert "FastAPI 依赖 Pydantic" in msgs[1]["content"]


def test_specialized_prompt_carries_language_and_restricts_entities():
    msgs = build_messages(
        "def run():\n    return FastAPI()",
        extraction_policy=ExtractionPolicy.SPECIALIZED,
        language="python",
    )
    combined = msgs[0]["content"] + msgs[1]["content"]
    assert "python" in combined
    assert "库" in combined or "framework" in combined.lower()
    assert "generic" in combined.lower() or "通用" in combined
