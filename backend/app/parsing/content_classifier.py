"""Deterministic classification of parser blocks."""

import re

from app.parsing.models import ContentKind, ExtractionPolicy

_CONFIG_LANGUAGES = {"json", "jsonc", "yaml", "yml", "toml"}
_LIST_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
_LOG_LINE = re.compile(
    r"^\s*(?:\[?\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}|\[?\d{2}:\d{2}:\d{2})\b"
)
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")


def classify_block(
    text: str, *, fenced_language: str | None = None
) -> tuple[ContentKind, str | None, ExtractionPolicy]:
    """Classify a block without invoking an LLM.

    A non-``None`` *fenced_language* marks the block as fenced, including an
    empty info string for an unlabeled fence.  Language names are normalized
    to lowercase and only the first info-string token is retained by callers.
    """
    if fenced_language is not None:
        language = fenced_language.strip().split(maxsplit=1)[0].lower() or None
        if language in _CONFIG_LANGUAGES:
            return ContentKind.CONFIG, language, ExtractionPolicy.SKIP
        return ContentKind.CODE, language, ExtractionPolicy.SPECIALIZED

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2 and _TABLE_SEPARATOR.match(lines[1]) and "|" in lines[0]:
        return ContentKind.TABLE, None, ExtractionPolicy.NORMAL
    if lines and all(_LIST_LINE.match(line) for line in lines):
        return ContentKind.LIST, None, ExtractionPolicy.NORMAL
    if lines and all(_LOG_LINE.match(line) for line in lines):
        return ContentKind.LOG, None, ExtractionPolicy.SKIP
    return ContentKind.PROSE, None, ExtractionPolicy.NORMAL
