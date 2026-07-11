import pytest

from evals.metrics import (
    count_entity_recall_sample,
    split_assertion_sentences,
    summarize_entity_recall,
)


def test_preserves_dotted_identifiers_versions_urls_and_citations():
    text = "Cytoscape.js 用于图谱 [1]。React 19.2 可用 [2]。详见 https://example.com/a.b [3]。"
    assert split_assertion_sentences(text) == [
        "Cytoscape.js 用于图谱 [1]。",
        "React 19.2 可用 [2]。",
        "详见 https://example.com/a.b [3]。",
    ]


def test_markdown_lists_are_independent_and_fences_are_ignored():
    text = "- 第一项 [1]\n- 第二项 [2]\n```ts\nconst x = 'no claim'\n```"
    assert split_assertion_sentences(text) == ["第一项 [1]", "第二项 [2]"]


def test_splits_english_period_without_splitting_url_query():
    text = "See https://example.com/a.b?q=1.2 [1]. Next claim [2]."
    assert split_assertion_sentences(text) == [
        "See https://example.com/a.b?q=1.2 [1].",
        "Next claim [2].",
    ]


def test_url_trailing_period_stays_a_sentence_boundary_before_citation():
    text = "See https://example.com/a.b.[1] Next claim [2]."
    assert split_assertion_sentences(text) == [
        "See https://example.com/a.b.[1]",
        "Next claim [2].",
    ]


def test_url_query_keeps_internal_punctuation_but_not_trailing_period():
    text = "See https://example.com/a.b?q=1.2.[1] Next claim [2]."
    assert split_assertion_sentences(text) == [
        "See https://example.com/a.b?q=1.2.[1]",
        "Next claim [2].",
    ]


def test_ellipsis_is_one_boundary_and_keeps_its_citation():
    assert split_assertion_sentences("Wait... [1] Next [2].") == [
        "Wait... [1]",
        "Next [2].",
    ]


def test_mixed_terminal_run_is_one_boundary_and_keeps_its_citation():
    assert split_assertion_sentences("Really?! [1] Next [2].") == [
        "Really?! [1]",
        "Next [2].",
    ]


def test_punctuation_only_fragments_are_not_assertions():
    text = "... [1]\n?! [2]\nClaim [3]."
    assert split_assertion_sentences(text) == ["Claim [3]."]


def test_entity_recall_reports_pooled_and_macro():
    pooled, macro = summarize_entity_recall([8, 1], [10, 2])
    assert pooled == 0.75
    assert macro == 0.65


def test_parse_failed_document_counts_as_zero_hits():
    assert count_entity_recall_sample(["Alpha", " alpha ", "Beta"], None) == (0, 2)


def test_entity_recall_rejects_mismatched_count_lists():
    with pytest.raises(ValueError, match="equal lengths"):
        summarize_entity_recall([1], [1, 2])


def test_entity_recall_empty_input_returns_zeroes():
    assert summarize_entity_recall([], []) == (0.0, 0.0)


def test_zero_gold_document_is_zero_in_macro_and_neutral_in_pooled():
    pooled, macro = summarize_entity_recall([0, 1], [0, 2])
    assert pooled == 0.5
    assert macro == 0.25
