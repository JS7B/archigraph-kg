"""问答数据模型：检索证据、实体关系路径、引用、答案。

对外响应模型（Answer/Citation）带 camelCase alias，路由用 model_dump(by_alias=True)
输出前端期望的 camelCase；内部仍用 snake_case 字段名。
"""

from pydantic import BaseModel, ConfigDict, Field


def _camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _CamelModel(BaseModel):
    """对外响应基类：序列化用 camelCase alias，构造时仍可用 snake_case。"""

    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class Citation(_CamelModel):
    """答案引用：角标号 + 来源 chunk + 可读位置 + 片段。"""

    index: int  # 答案正文角标，从 1 起
    chunk_id: str
    document_id: str
    location: str  # 由 page / heading_path / 字符区间拼成的可读串
    snippet: str


class Answer(_CamelModel):
    """一次问答的结果。"""

    text: str
    confidence: str  # high / medium / low
    citations: list[Citation] = Field(default_factory=list)


class RelationPath(BaseModel):
    """一条实体关系路径（1 跳），用于答案展示与上下文。"""

    source_name: str
    target_name: str
    type: str
    evidence_chunk_id: str


class RetrievalContext(BaseModel):
    """邻域扩展产出的证据集：实体关系路径。"""

    paths: list[RelationPath] = Field(default_factory=list)
