import re
import unicodedata
from difflib import SequenceMatcher

from unidecode import unidecode


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_diacritics = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    normalized = unidecode(without_diacritics)
    return re.sub(r"\s+", " ", normalized.strip())


def text_similarity(query: str, *values: str) -> float:
    normalized_query = normalize_text(query)
    candidates = {
        candidate
        for value in values
        for candidate in _comparison_candidates(normalize_text(value))
    }
    return max(
        SequenceMatcher(None, normalized_query, candidate).ratio()
        for candidate in candidates
    )


def _comparison_candidates(value: str) -> set[str]:
    return {value, *value.split()}
