"""Stable normalization keys used by deterministic entity resolution."""

import unicodedata


def normalize_name(value: str) -> str:
    """Normalize Unicode forms, case, punctuation, and whitespace idempotently."""

    if not isinstance(value, str):
        raise TypeError("name must be a string")
    normalized = unicodedata.normalize("NFKC", value).casefold()
    without_punctuation = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("P")
    )
    return " ".join(without_punctuation.split())


normalize_key = normalize_name
