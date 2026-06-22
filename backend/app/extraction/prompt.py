"""抽取 prompt 构造。

json_object 模式要求 prompt 文本出现 "json" 字样，system 与 user 均显式声明。
实体/关系类型给候选但不强制——围绕样本收敛，避免堆无用类型。
"""

SYSTEM_PROMPT = (
    "你是知识图谱抽取助手。从给定文本片段中识别实体与它们之间的关系，"
    "只输出一个 JSON 对象，不要 markdown、不要解释。\n"
    "JSON 形如 {\"entities\": [...], \"relations\": [...]}。\n"
    "entity 字段：name（实体名）、type（类型，优先从 人物/机构/项目/技术概念/"
    "产品模块/指标/风险点/需求项 中选，没有合适的可自拟）、description（依据本片段的一句话描述）。\n"
    "relation 字段：source、target（都必须精确等于本次 entities 中某个 name）、"
    "type（优先从 依赖/组成/使用/导致/缓解/属于/对比/影响/约束 中选）、confidence（0~1 的把握度）。\n"
    "片段中没有可抽取内容时，返回空数组。"
)


def build_messages(chunk_text: str) -> list[dict]:
    """构造单个 chunk 的抽取消息（system + user）。"""
    user = (
        "请从下面的文本片段抽取实体与关系，并以 JSON 对象返回，"
        '形如 {"entities": [{"name":"...","type":"...","description":"..."}], '
        '"relations": [{"source":"...","target":"...","type":"...","confidence":0.8}]}。\n'
        "relations 的 source/target 必须是 entities 中出现过的 name。\n\n"
        f"文本片段：\n{chunk_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
