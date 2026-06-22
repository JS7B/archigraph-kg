"""真实 LLM 抽取：仅在 LLM 已配置时运行，否则 skip。"""

import pytest

from app.clients.llm import is_configured
from app.extraction.llm_extract import extract_chunk

pytestmark = pytest.mark.skipif(
    not is_configured(), reason="LLM 未配置，跳过真实抽取测试"
)


def test_real_extraction_produces_entities():
    text = "FastAPI 是一个 Python Web 框架，它依赖 Pydantic 做数据校验和结构化输出。"
    result = extract_chunk("test_real#0", text)
    assert len(result.entities) >= 1
    names = [e.name for e in result.entities]
    # 不强断言具体名字（LLM 有波动），只验证结构与至少抽到内容
    assert all(e.name and e.type for e in result.entities)
    assert "FastAPI" in " ".join(names) or "Pydantic" in " ".join(names)
