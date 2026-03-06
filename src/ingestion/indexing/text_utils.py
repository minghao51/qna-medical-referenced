"""Text processing helpers for vector indexing/search."""

import hashlib
import re

from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer

ENGLISH_STOPWORDS = set(stopwords.words("english"))

MEDICAL_STOPWORDS = {
    "patient", "patients", "year", "years", "month", "months",
    "old", "male", "female", "gender", "age", "case", "cases",
    "study", "group", "result", "results", "data", "analysis",
    "method", "methods", "background", "objective", "conclusion",
}
ALL_STOPWORDS = ENGLISH_STOPWORDS | MEDICAL_STOPWORDS

STEMMER = SnowballStemmer("english")

MAX_TEXT_LENGTH = 50000
DANGEROUS_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WORD_PATTERN = re.compile(r"\b[\w-]+\b")
UNIT_NORMALIZATIONS = {
    "mmol/l": "mmoll",
    "mg/dl": "mgdl",
    "kg/m2": "kgm2",
    "%": "percent",
}
MEDICAL_SYNONYMS = {
    "ldl-c": "ldlc",
    "ldl": "ldlc",
    "cholesterol": "lipid",
    "familial-hypercholesterolemia": "fh",
    "atherosclerotic": "ascvd",
}
ACRONYM_EXPANSIONS = {
    "fh": ["familial", "hypercholesterolemia"],
    "ascvd": ["atherosclerotic", "cardiovascular", "disease"],
    "ldlc": ["ldl", "cholesterol"],
}


def sanitize_text(text: str) -> str:
    text = DANGEROUS_CHARS_PATTERN.sub("", text)
    for raw, replacement in UNIT_NORMALIZATIONS.items():
        text = text.replace(raw, replacement).replace(raw.upper(), replacement)
    text = text[:MAX_TEXT_LENGTH]
    return text.strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _get_words(text: str) -> list[str]:
    words = WORD_PATTERN.findall(text.lower())
    result: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        if i + 1 < len(words) and word.endswith("-"):
            word = word + words[i + 1]
            i += 1
        result.append(word)
        i += 1
    return result


def _should_stem(word: str) -> bool:
    if not word:
        return False
    if "-" in word:
        return False
    if word.isupper() and len(word) > 1:
        return False
    if len(word) <= 2:
        return False
    return True


def _preprocess_word(word: str) -> str:
    normalized = word.lower()
    normalized = MEDICAL_SYNONYMS.get(normalized, normalized)
    if _should_stem(normalized):
        return STEMMER.stem(normalized)
    return normalized


def tokenize_text(text: str) -> list[str]:
    filtered: list[str] = []
    for word in _get_words(text):
        if word in ALL_STOPWORDS:
            continue
        if word.replace("-", "").isalpha():
            normalized = _preprocess_word(word)
            filtered.append(normalized)
            for expansion in ACRONYM_EXPANSIONS.get(normalized, []):
                expanded = _preprocess_word(expansion)
                if expanded not in filtered:
                    filtered.append(expanded)
    return filtered
