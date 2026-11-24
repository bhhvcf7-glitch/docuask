import re
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.text import normalize_arabic

_ARABIC_WORD = re.compile(r"[\u0621-\u064a]+")
_UNMAPPED_CID = re.compile(r"\(cid:\d+\)")
_WORDS = frozenset(
    word.strip()
    for word in Path(__file__).with_name("arabic_words.txt").read_text(encoding="utf-8").splitlines()
    if word.strip()
)


@dataclass(frozen=True)
class ArabicQuality:
    issues: tuple[str, ...]
    unreliable: bool


def inspect_arabic(text: str) -> ArabicQuality:
    issues: list[str] = []
    if any(
        "\ufb50" <= char <= "\ufdff" or "\ufe70" <= char <= "\ufefc"
        for char in text
    ):
        issues.append("presentation_forms")

    plain = normalize_arabic(text)
    words = _ARABIC_WORD.findall(plain)
    forward = sum(word in _WORDS for word in words)
    reversed_words = sum(
        word[::-1] in _WORDS and word not in _WORDS
        for word in words
    )
    if reversed_words >= 3 and reversed_words >= 3 * max(forward, 1):
        issues.append("suspected_reversed_words")

    isolated = sum(len(word) == 1 for word in words)
    if len(words) >= 10 and isolated >= 8 and isolated / len(words) >= 0.75:
        issues.append("disconnected_letters")

    unreadable = len(_UNMAPPED_CID.findall(text))
    replacements = text.count("\ufffd")
    if unreadable >= 3 or replacements >= 3 and replacements / max(len(text), 1) >= 0.1:
        issues.append("unmapped_glyphs")

    return ArabicQuality(
        issues=tuple(issues),
        unreliable=any(
            issue in issues
            for issue in ("suspected_reversed_words", "disconnected_letters", "unmapped_glyphs")
        ),
    )
