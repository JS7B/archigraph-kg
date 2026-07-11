"""文档解析与切块：文件/目录 → 带来源元数据的 Chunk 列表。"""

from app.parsing.base import parse_file
from app.parsing.errors import ParseError
from app.parsing.models import (
    Block,
    Chunk,
    ContentKind,
    ExtractionPolicy,
    ParsedDocument,
    SourceLocation,
)
from app.parsing.repo_importer import parse_directory

__all__ = [
    "parse_file",
    "parse_directory",
    "ParseError",
    "ParsedDocument",
    "Chunk",
    "Block",
    "SourceLocation",
    "ContentKind",
    "ExtractionPolicy",
]
