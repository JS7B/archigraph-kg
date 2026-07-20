"""共享答案 finalizer 的确定性边界测试。"""

from app.qa.finalize import NO_EVIDENCE_ANSWER, finalize_answer
from app.qa.models import Citation


def _citation(index: int) -> Citation:
    return Citation(
        index=index,
        chunk_id=f"d#{index}",
        document_id="d",
        location=f"字符 {index}-{index + 1}",
        snippet=f"片段{index}",
    )


def test_valid_duplicate_and_missing_markers_use_unique_valid_citations():
    answer = finalize_answer(
        "同一证据重复出现 [2][2]，另一条证据未引用。",
        [_citation(1), _citation(2), _citation(3)],
    )

    assert answer.text == "同一证据重复出现 [2][2]，另一条证据未引用。"
    assert [citation.index for citation in answer.citations] == [2]
    assert answer.confidence == "medium"


def test_citations_follow_context_order_not_written_order():
    answer = finalize_answer(
        "先写第三条 [3]，再写第一条 [1]。",
        [_citation(1), _citation(2), _citation(3)],
    )

    assert [citation.index for citation in answer.citations] == [1, 3]
    assert answer.confidence == "high"


def test_zero_and_out_of_range_markers_are_removed_and_cannot_raise_confidence():
    answer = finalize_answer(
        "没有有效证据 [0]，也没有第九条 [9]。",
        [_citation(1), _citation(2)],
    )

    assert answer.text == NO_EVIDENCE_ANSWER
    assert answer.citations == []
    assert answer.confidence == "low"


def test_missing_marker_replaces_uncited_factual_text_with_fixed_refusal():
    answer = finalize_answer(
        "这是一段没有任何引用的事实性回答。",
        [_citation(1), _citation(2)],
    )

    assert answer.text == NO_EVIDENCE_ANSWER
    assert answer.citations == []
    assert answer.confidence == "low"


def test_mixed_valid_and_invalid_markers_are_sanitized_and_capped_at_medium():
    answer = finalize_answer(
        "有效 [1] 与 [2]，无效 [0] 和 [99]。",
        [_citation(1), _citation(2), _citation(3)],
    )

    assert answer.text == "有效 [1] 与 [2]，无效  和 。"
    assert [citation.index for citation in answer.citations] == [1, 2]
    assert answer.confidence == "medium"


def test_markers_inside_inline_and_fenced_code_are_not_citations_or_rewritten():
    text = (
        "行内 `items[0] 与 [1]` 保持原样。\n"
        "```python\n"
        "values = [0], [2], [99]\n"
        "```\n"
        "正文引用 [2]，正文越界 [99]。"
    )

    answer = finalize_answer(text, [_citation(1), _citation(2)])

    assert answer.text == (
        "行内 `items[0] 与 [1]` 保持原样。\n"
        "```python\n"
        "values = [0], [2], [99]\n"
        "```\n"
        "正文引用 [2]，正文越界 。"
    )
    assert [citation.index for citation in answer.citations] == [2]
    assert answer.confidence == "medium"


def test_single_backtick_code_span_can_cross_lines_without_rewriting_markers():
    text = "`code\n[99]\n`\n正文 [1]"

    answer = finalize_answer(text, [_citation(1)])

    assert answer.text == text
    assert [citation.index for citation in answer.citations] == [1]
    assert answer.confidence == "medium"


def test_multi_backtick_code_span_can_cross_lines_without_rewriting_markers():
    text = "``code with ` delimiter\n[0] 与 [99]\n``\n正文 [1]"

    answer = finalize_answer(text, [_citation(1)])

    assert answer.text == text
    assert [citation.index for citation in answer.citations] == [1]
    assert answer.confidence == "medium"


def test_odd_backslash_escapes_opening_backticks():
    text = r"\`literal [1][2]\`，正文无效 [99]。"

    answer = finalize_answer(text, [_citation(1), _citation(2)])

    assert answer.text == r"\`literal [1][2]\`，正文无效 。"
    assert [citation.index for citation in answer.citations] == [1, 2]
    assert answer.confidence == "medium"


def test_even_backslashes_allow_opening_and_backslash_does_not_escape_closing():
    text = r"\\`code [99]\`，正文无效 [88]，依据 [1][2]。"

    answer = finalize_answer(text, [_citation(1), _citation(2)])

    assert answer.text == r"\\`code [99]\`，正文无效 ，依据 [1][2]。"
    assert [citation.index for citation in answer.citations] == [1, 2]
    assert answer.confidence == "medium"


def test_indented_code_blocks_do_not_contribute_or_rewrite_markers():
    text = (
        "正文依据 [1][2]。\n"
        "    spaces = [0], [99]\n"
        "\ttabbed = [0], [88]\n"
        "正文收尾。"
    )

    answer = finalize_answer(text, [_citation(1), _citation(2)])

    assert answer.text == (
        "正文依据 [1][2]。\n"
        "    spaces = [0], [99]\n"
        "\ttabbed = [0], [88]\n"
        "正文收尾。"
    )
    assert [citation.index for citation in answer.citations] == [1, 2]
    assert answer.confidence == "high"


def test_code_only_markers_do_not_prevent_fixed_refusal():
    answer = finalize_answer(
        "示例：`[1]`。\n~~~text\n[2]\n~~~",
        [_citation(1), _citation(2)],
    )

    assert answer.text == NO_EVIDENCE_ANSWER
    assert answer.citations == []
    assert answer.confidence == "low"


def test_non_integer_brackets_are_left_untouched():
    text = (
        "数组 [first]、范围 [-1]、小数 [1.5]、组合 [1,2]、"
        "带空格 [ 1 ] 和非 ASCII 数字 [١] 不是引用；依据 [1]。"
    )

    answer = finalize_answer(text, [_citation(1), _citation(2)])

    assert answer.text == text
    assert [citation.index for citation in answer.citations] == [1]


def test_extremely_long_numeric_marker_is_removed_without_integer_conversion():
    marker = "9" * 5000

    answer = finalize_answer(
        f"有效 [1]，无效 [{marker}]。",
        [_citation(1)],
    )

    assert answer.text == "有效 [1]，无效 。"
    assert [citation.index for citation in answer.citations] == [1]
    assert answer.confidence == "medium"
