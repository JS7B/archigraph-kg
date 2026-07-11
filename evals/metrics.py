"""Deterministic helpers for evaluation metrics."""

import re
from statistics import mean


_PROTECTED_DOT = "\ue000"
_PROTECTED_QUESTION = "\ue001"
_PROTECTED_EXCLAMATION = "\ue002"
_DOTTED_TOKEN_RE = re.compile(r"(?<=\w)\.(?=\w)")
_URL_RE = re.compile(r"https?://\S+")
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_PURE_FORMAT_RE = re.compile(r"[\s#>*_~`-]+")
_SENTENCE_END_RE = re.compile(r"[。.！!？?.](?:\s*\[\d+\])*")


def _protect_url_punctuation(match: re.Match[str]) -> str:
    url = match.group(0)
    protected = []
    sentinels = {
        ".": _PROTECTED_DOT,
        "?": _PROTECTED_QUESTION,
        "!": _PROTECTED_EXCLAMATION,
    }
    for index, char in enumerate(url):
        protected.append(sentinels.get(char, char) if index < len(url) - 1 else char)
    return "".join(protected)


def _restore_protected_punctuation(text: str) -> str:
    return (
        text.replace(_PROTECTED_DOT, ".")
        .replace(_PROTECTED_QUESTION, "?")
        .replace(_PROTECTED_EXCLAMATION, "!")
    )


def split_assertion_sentences(text: str) -> list[str]:
    """Split answer Markdown into citation-preserving assertion sentences."""
    sentences: list[str] = []
    in_fence = False

    for raw_line in text.splitlines():
        if re.match(r"^\s*(?:```|~~~)", raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        line = _LIST_PREFIX_RE.sub("", raw_line.strip())
        line = _URL_RE.sub(_protect_url_punctuation, line)
        protected = _DOTTED_TOKEN_RE.sub(_PROTECTED_DOT, line)
        start = 0
        fragments = []
        for match in _SENTENCE_END_RE.finditer(protected):
            fragments.append(protected[start : match.end()])
            start = match.end()
        fragments.append(protected[start:])

        for fragment in fragments:
            sentence = _restore_protected_punctuation(fragment).strip()
            if sentence and not _PURE_FORMAT_RE.fullmatch(sentence):
                sentences.append(sentence)

    return sentences


def summarize_entity_recall(
    hit_counts: list[int], gold_counts: list[int]
) -> tuple[float, float]:
    """Return annotation-pooled and per-document macro entity recall."""
    if len(hit_counts) != len(gold_counts):
        raise ValueError("hit_counts and gold_counts must have equal lengths")
    if not hit_counts:
        return 0.0, 0.0

    total_gold = sum(gold_counts)
    pooled = sum(hit_counts) / total_gold if total_gold else 0.0
    macro = mean(
        hits / gold if gold else 0.0
        for hits, gold in zip(hit_counts, gold_counts, strict=True)
    )
    return pooled, macro
