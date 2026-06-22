"""抽取领域异常：沿用 parsing.errors.ParseError 模式。"""


class ExtractionError(Exception):
    """单个 chunk 抽取重试耗尽后抛出。"""

    def __init__(self, chunk_id: str, reason: str) -> None:
        self.chunk_id = chunk_id
        self.reason = reason
        super().__init__(f"抽取失败 [{chunk_id}]: {reason}")
