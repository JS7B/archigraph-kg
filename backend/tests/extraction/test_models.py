"""抽取模型校验：正常解析、缺字段用默认、confidence 缺省。"""

from app.extraction.models import ChunkExtractionResult


def test_parses_full_payload():
    data = {
        "entities": [{"name": "FastAPI", "type": "技术概念", "description": "Web 框架"}],
        "relations": [
            {"source": "FastAPI", "target": "Pydantic", "type": "依赖", "confidence": 0.9}
        ],
    }
    result = ChunkExtractionResult.model_validate(data)
    assert result.entities[0].name == "FastAPI"
    assert result.relations[0].confidence == 0.9


def test_empty_arrays_default():
    result = ChunkExtractionResult.model_validate({})
    assert result.entities == []
    assert result.relations == []


def test_entity_description_defaults_empty():
    result = ChunkExtractionResult.model_validate(
        {"entities": [{"name": "X", "type": "项目"}]}
    )
    assert result.entities[0].description == ""


def test_relation_confidence_defaults():
    result = ChunkExtractionResult.model_validate(
        {"relations": [{"source": "A", "target": "B", "type": "使用"}]}
    )
    assert result.relations[0].confidence == 0.5
