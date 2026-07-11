from evals.metrics import split_assertion_sentences, summarize_entity_recall


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


def test_entity_recall_reports_pooled_and_macro():
    pooled, macro = summarize_entity_recall([8, 1], [10, 2])
    assert pooled == 0.75
    assert macro == 0.65
