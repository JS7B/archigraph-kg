"""把模型生成文本收敛为可追溯的 Answer。"""

import re

from app.qa.models import Answer, Citation

NO_EVIDENCE_ANSWER = "根据现有资料无法回答。"

_MARKER_RE = re.compile(r"\[([0-9]+)\]")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_TOP_LEVEL_LIST_RE = re.compile(
    r"^ {0,3}(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)"
)


def _closing_fence(line: str, marker: str) -> bool:
    pattern = rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*(?:\r?\n)?$"
    return re.match(pattern, line) is not None


def _find_code_span_end(text: str, start: int, run_length: int) -> int | None:
    """查找长度完全相同的反引号闭合串。"""
    cursor = start + run_length
    marker = "`" * run_length
    while True:
        candidate = text.find(marker, cursor)
        if candidate < 0:
            return None
        before_is_tick = candidate > 0 and text[candidate - 1] == "`"
        after = candidate + run_length
        after_is_tick = after < len(text) and text[after] == "`"
        if not before_is_tick and not after_is_tick:
            return after
        cursor = after


def _opening_backticks_are_escaped(text: str, start: int) -> bool:
    backslashes = 0
    cursor = start - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def _sanitize_plain_text(
    text: str,
    available: set[str],
    written: set[str],
) -> tuple[str, bool]:
    had_invalid = False

    def replace(match: re.Match[str]) -> str:
        nonlocal had_invalid
        index = match.group(1).lstrip("0") or "0"
        written.add(index)
        if index == "0" or index not in available:
            had_invalid = True
            return ""
        return match.group(0)

    return _MARKER_RE.sub(replace, text), had_invalid


def _sanitize_code_spans(
    text: str,
    available: set[str],
    written: set[str],
) -> tuple[str, bool]:
    """清理普通文本角标，同时原样保留可跨行的 Markdown code span。"""
    output: list[str] = []
    had_invalid = False
    plain_start = 0
    cursor = 0

    while cursor < len(text):
        if text[cursor] != "`":
            cursor += 1
            continue

        run_end = cursor + 1
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        if _opening_backticks_are_escaped(text, cursor):
            cursor = run_end
            continue
        code_end = _find_code_span_end(text, cursor, run_end - cursor)
        if code_end is None:
            cursor = run_end
            continue

        plain, invalid = _sanitize_plain_text(
            text[plain_start:cursor], available, written
        )
        output.extend((plain, text[cursor:code_end]))
        had_invalid = had_invalid or invalid
        cursor = code_end
        plain_start = code_end

    plain, invalid = _sanitize_plain_text(text[plain_start:], available, written)
    output.append(plain)
    return "".join(output), had_invalid or invalid


def _sanitize_markers(text: str, available: set[str]) -> tuple[str, set[str], bool]:
    """一次扫描正文角标；Markdown code span/顶层代码块不参与引用语义。"""
    output: list[str] = []
    written: set[str] = set()
    had_invalid = False
    fence_marker: str | None = None
    plain_lines: list[str] = []
    at_document_start = True
    previous_line_blank = False
    in_indented_code = False
    in_list_container = False

    def flush_plain_lines() -> None:
        nonlocal had_invalid
        if not plain_lines:
            return
        sanitized, invalid = _sanitize_code_spans(
            "".join(plain_lines), available, written
        )
        output.append(sanitized)
        plain_lines.clear()
        had_invalid = had_invalid or invalid

    for line in text.splitlines(keepends=True):
        line_blank = not line.strip()
        line_indented = line.startswith("    ") or line.startswith("\t")

        if fence_marker is not None:
            output.append(line)
            if _closing_fence(line, fence_marker):
                fence_marker = None
            at_document_start = False
            previous_line_blank = line_blank
            continue

        if in_indented_code:
            if line_indented or line_blank:
                output.append(line)
                at_document_start = False
                previous_line_blank = line_blank
                continue
            in_indented_code = False

        opening = _FENCE_OPEN_RE.match(line)
        if opening:
            flush_plain_lines()
            fence_marker = opening.group(1)
            in_list_container = False
            output.append(line)
            at_document_start = False
            previous_line_blank = line_blank
            continue

        if _TOP_LEVEL_LIST_RE.match(line):
            in_list_container = True
            plain_lines.append(line)
        elif in_list_container and (line_blank or line_indented):
            plain_lines.append(line)
        else:
            if in_list_container:
                in_list_container = False
            if line_indented and (at_document_start or previous_line_blank):
                flush_plain_lines()
                in_indented_code = True
                output.append(line)
            else:
                plain_lines.append(line)

        at_document_start = False
        previous_line_blank = line_blank

    flush_plain_lines()
    return "".join(output), written, had_invalid


def finalize_answer(text: str, citations: list[Citation]) -> Answer:
    """校验模型角标，并按上下文顺序返回唯一、真实可用的 Citation。"""
    available = {str(citation.index) for citation in citations if citation.index > 0}
    sanitized, written, had_invalid = _sanitize_markers(text, available)
    valid_used = written & available

    if not valid_used:
        return Answer(text=NO_EVIDENCE_ANSWER, confidence="low", citations=[])

    cited: list[Citation] = []
    seen: set[int] = set()
    for citation in citations:
        if str(citation.index) in valid_used and citation.index not in seen:
            cited.append(citation)
            seen.add(citation.index)

    confidence = "high" if len(valid_used) >= 2 else "medium"
    if had_invalid:
        confidence = "medium"
    return Answer(text=sanitized, confidence=confidence, citations=cited)
