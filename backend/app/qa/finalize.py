"""把模型生成文本收敛为可追溯的 Answer。"""

import re

from app.qa.models import Answer, Citation

NO_EVIDENCE_ANSWER = "根据现有资料无法回答。"

_MARKER_RE = re.compile(r"\[([0-9]+)\]")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _closing_fence(line: str, marker: str) -> bool:
    pattern = rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*(?:\r?\n)?$"
    return re.match(pattern, line) is not None


def _find_code_span_end(line: str, start: int, run_length: int) -> int | None:
    """查找长度完全相同的反引号闭合串。"""
    cursor = start + run_length
    marker = "`" * run_length
    while True:
        candidate = line.find(marker, cursor)
        if candidate < 0:
            return None
        before_is_tick = candidate > 0 and line[candidate - 1] == "`"
        after = candidate + run_length
        after_is_tick = after < len(line) and line[after] == "`"
        if not before_is_tick and not after_is_tick:
            return after
        cursor = after


def _sanitize_plain_text(
    text: str,
    available: set[int],
    written: set[int],
) -> tuple[str, bool]:
    had_invalid = False

    def replace(match: re.Match[str]) -> str:
        nonlocal had_invalid
        index = int(match.group(1))
        written.add(index)
        if index <= 0 or index not in available:
            had_invalid = True
            return ""
        return match.group(0)

    return _MARKER_RE.sub(replace, text), had_invalid


def _sanitize_inline_code(
    line: str,
    available: set[int],
    written: set[int],
) -> tuple[str, bool]:
    """清理普通文本角标，同时原样保留 Markdown 行内代码。"""
    output: list[str] = []
    had_invalid = False
    plain_start = 0
    cursor = 0

    while cursor < len(line):
        if line[cursor] != "`":
            cursor += 1
            continue

        run_end = cursor + 1
        while run_end < len(line) and line[run_end] == "`":
            run_end += 1
        code_end = _find_code_span_end(line, cursor, run_end - cursor)
        if code_end is None:
            cursor = run_end
            continue

        plain, invalid = _sanitize_plain_text(
            line[plain_start:cursor], available, written
        )
        output.extend((plain, line[cursor:code_end]))
        had_invalid = had_invalid or invalid
        cursor = code_end
        plain_start = code_end

    plain, invalid = _sanitize_plain_text(line[plain_start:], available, written)
    output.append(plain)
    return "".join(output), had_invalid or invalid


def _sanitize_markers(text: str, available: set[int]) -> tuple[str, set[int], bool]:
    """一次扫描正文角标；Markdown code span/fence 不参与引用语义。"""
    output: list[str] = []
    written: set[int] = set()
    had_invalid = False
    fence_marker: str | None = None

    for line in text.splitlines(keepends=True):
        if fence_marker is not None:
            output.append(line)
            if _closing_fence(line, fence_marker):
                fence_marker = None
            continue

        opening = _FENCE_OPEN_RE.match(line)
        if opening:
            fence_marker = opening.group(1)
            output.append(line)
            continue

        sanitized, invalid = _sanitize_inline_code(line, available, written)
        output.append(sanitized)
        had_invalid = had_invalid or invalid

    return "".join(output), written, had_invalid


def finalize_answer(text: str, citations: list[Citation]) -> Answer:
    """校验模型角标，并按上下文顺序返回唯一、真实可用的 Citation。"""
    available = {citation.index for citation in citations if citation.index > 0}
    sanitized, written, had_invalid = _sanitize_markers(text, available)
    valid_used = written & available

    if not valid_used:
        return Answer(text=NO_EVIDENCE_ANSWER, confidence="low", citations=[])

    cited: list[Citation] = []
    seen: set[int] = set()
    for citation in citations:
        if citation.index in valid_used and citation.index not in seen:
            cited.append(citation)
            seen.add(citation.index)

    confidence = "high" if len(valid_used) >= 2 else "medium"
    if had_invalid:
        confidence = "medium"
    return Answer(text=sanitized, confidence=confidence, citations=cited)
