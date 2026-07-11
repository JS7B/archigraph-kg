"""抽取 prompt 构造。

json_object 模式要求 prompt 文本出现 "json" 字样，system 与 user 均显式声明。
实体类型为封闭集合（模型不得自拟），并给出排除清单、枚举展开指令与中英混合 few-shot，
从源头压噪、提召回（技术栈列举漏抽是主要失分点）。JSON 输出结构不变，下游模型不动。
"""

from app.parsing.models import ExtractionPolicy

# 封闭实体类型集合：不属于任何一类则不抽取（禁止模型自拟新类型）。
ENTITY_TYPES = "人物、机构、项目、技术、概念、产品模块、指标、需求项、风险点"

SYSTEM_PROMPT = (
    "你是知识图谱抽取助手。从给定文本片段中识别实体与它们之间的关系，"
    "只输出一个 JSON 对象，不要 markdown、不要解释。\n"
    "JSON 形如 {\"entities\": [...], \"relations\": [...]}。\n"
    "entity 字段：name（实体名）、type（类型）、description（依据本片段的一句话描述）。\n"
    f"type 只能取以下封闭集合之一：{ENTITY_TYPES}。不属于任何一类的，不要抽取，"
    "严禁自拟新类型。\n"
    "不要抽取以下内容（它们不是实体）：代词（它/这/该系统等）、章节标题、"
    "泛化名词（如「系统」「项目」「功能」「用户」「数据」「服务」这类不指向具体对象的词）、"
    "动词短语、整句式描述。\n"
    "枚举展开：当文本用顿号/斜杠/逗号列举技术栈、依赖或工具时，其中每一个具名的"
    "技术、库、框架、语言、组件都要各自单独成为一个实体（例如 "
    "「Python / FastAPI / React + Vite + TypeScript」应抽出 Python、FastAPI、React、"
    "Vite、TypeScript 五个实体，而不是一个笼统的「技术栈」）。\n"
    "英文术语保留原始拼写与大小写（写 Neo4j 不写 neo4j，写 TypeScript 不写 typescript）。\n"
    "relation 字段：source、target（都必须精确等于本次 entities 中某个 name）、"
    "type（优先从 依赖/组成/使用/导致/缓解/属于/对比/影响/约束 中选）、confidence（0~1 的把握度）。\n"
    "片段中没有可抽取内容时，返回空数组。\n"
    "示例——文本「本系统基于 Python 与 FastAPI 构建，用它做后端服务」应抽取："
    "{\"entities\": [{\"name\": \"Python\", \"type\": \"技术\", \"description\": \"构建本系统的编程语言\"}, "
    "{\"name\": \"FastAPI\", \"type\": \"技术\", \"description\": \"后端服务框架\"}], "
    "\"relations\": [{\"source\": \"FastAPI\", \"target\": \"Python\", \"type\": \"依赖\", \"confidence\": 0.8}]}——"
    "注意「本系统」「后端服务」「它」是泛化名词/代词，不抽取。"
)


def build_messages(
    chunk_text: str,
    *,
    extraction_policy: ExtractionPolicy | str = ExtractionPolicy.NORMAL,
    language: str | None = None,
) -> list[dict]:
    """构造单个 chunk 的抽取消息（system + user）。"""
    try:
        policy = ExtractionPolicy(extraction_policy)
    except ValueError:
        policy = ExtractionPolicy.NORMAL
    system = SYSTEM_PROMPT
    if policy is ExtractionPolicy.SPECIALIZED:
        system += (
            "\nThis is a code/config specialized chunk. Extract only explicitly named "
            "libraries, frameworks, languages, tools, or components. Reject generic "
            "syntax, paths, log lines, punctuation, symbols, and variable names as entities."
        )
    language_hint = f"\nDetected language: {language}" if language else ""
    user = (
        "请从下面的文本片段抽取实体与关系，并以 JSON 对象返回，"
        '形如 {"entities": [{"name":"...","type":"...","description":"..."}], '
        '"relations": [{"source":"...","target":"...","type":"...","confidence":0.8}]}。\n'
        "relations 的 source/target 必须是 entities 中出现过的 name。\n\n"
        f"文本片段：\n{chunk_text}{language_hint}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
