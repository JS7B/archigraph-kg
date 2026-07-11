from app.parsing.content_classifier import classify_block
from app.parsing.models import ContentKind, ExtractionPolicy


def test_python_fence_is_specialized_code():
    assert classify_block("print('hi')", fenced_language="python") == (
        ContentKind.CODE,
        "python",
        ExtractionPolicy.SPECIALIZED,
    )


def test_json_fence_is_skipped_config():
    assert classify_block('{"port": 8000}', fenced_language="json") == (
        ContentKind.CONFIG,
        "json",
        ExtractionPolicy.SKIP,
    )


def test_markdown_table_is_normal_table():
    assert classify_block("| name | value |\n| --- | --- |\n| a | 1 |") == (
        ContentKind.TABLE,
        None,
        ExtractionPolicy.NORMAL,
    )


def test_bullet_list_is_normal_list():
    assert classify_block("- first\n- second") == (
        ContentKind.LIST,
        None,
        ExtractionPolicy.NORMAL,
    )


def test_timestamped_lines_are_skipped_logs():
    assert classify_block("2026-07-12 12:34:56 INFO worker started") == (
        ContentKind.LOG,
        None,
        ExtractionPolicy.SKIP,
    )


def test_ordinary_paragraph_is_normal_prose():
    assert classify_block("Knowledge graphs connect related concepts.") == (
        ContentKind.PROSE,
        None,
        ExtractionPolicy.NORMAL,
    )


def test_unknown_fence_defaults_to_specialized_code():
    assert classify_block("opaque content", fenced_language="custom-lang") == (
        ContentKind.CODE,
        "custom-lang",
        ExtractionPolicy.SPECIALIZED,
    )


def test_unlabeled_fence_defaults_to_specialized_code():
    assert classify_block("opaque content", fenced_language="") == (
        ContentKind.CODE,
        None,
        ExtractionPolicy.SPECIALIZED,
    )
