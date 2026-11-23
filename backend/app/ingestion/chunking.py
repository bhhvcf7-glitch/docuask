import re
from dataclasses import dataclass

from app.ingestion.text import normalize_arabic

_SENTENCE_BREAK = re.compile(
    r"(?<=[.!?؟،؛;:])\s+"
    r"|(?<=[؟،؛])(?=\S)"
    r"|(?<=[.!?;:])(?=[A-Z\u0600-\u06ff])"
)


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    page_number: int
    original_text: str
    normalized_text: str


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _sentences(paragraph: str) -> list[str]:
    text = " ".join(paragraph.split())
    return [part.strip() for part in _SENTENCE_BREAK.split(text) if part.strip()]


def _units(paragraph: str, max_chars: int) -> list[str]:
    units: list[str] = []
    for sentence in _sentences(paragraph):
        if len(sentence) <= max_chars:
            units.append(sentence)
            continue
        # Only sentences larger than a chunk need word-level splitting.
        for word in sentence.split():
            units.extend(
                word[start : start + max_chars]
                for start in range(0, len(word), max_chars)
            )
    return units


def _overlap(text: str, overlap_chars: int) -> str:
    if not overlap_chars:
        return ""
    tail: list[str] = []
    for word in reversed(text.split()):
        candidate = " ".join([word, *tail])
        if len(candidate) > overlap_chars:
            break
        tail.insert(0, word)
    return " ".join(tail)


def chunk_pages(
    pages: list[tuple[int, str]], *, max_chars: int = 900, overlap_chars: int = 120
) -> list[TextChunk]:
    if max_chars < 16 or overlap_chars < 0 or overlap_chars >= max_chars // 2:
        raise ValueError("Invalid chunk size or overlap")

    chunks: list[TextChunk] = []
    for page_number, page_text in pages:
        if page_number < 1:
            raise ValueError("Page numbers are one-based")

        def append(text: str, number: int) -> None:
            if text:
                chunks.append(
                    TextChunk(
                        ordinal=len(chunks),
                        page_number=number,
                        original_text=text,
                        normalized_text=normalize_arabic(text),
                    )
                )

        # No chunks or overlap span pages or paragraph breaks.
        for paragraph in _paragraphs(page_text):
            current = ""
            for unit in _units(paragraph, max_chars):
                if current and len(current) + 1 + len(unit) > max_chars:
                    append(current, page_number)
                    current = _overlap(current, overlap_chars)
                    while current and len(current) + 1 + len(unit) > max_chars:
                        current = " ".join(current.split()[1:])
                current = f"{current} {unit}".strip()
            append(current, page_number)

    return chunks
