import re
from dataclasses import dataclass

from app.ingestion.text import normalize_arabic


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    page_number: int
    original_text: str
    normalized_text: str


def _sections(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _words(text: str, max_chars: int) -> list[str]:
    words: list[str] = []
    for word in text.split():
        words.extend(word[i : i + max_chars] for i in range(0, len(word), max_chars))
    return words


def _overlap(words: list[str], overlap_chars: int) -> list[str]:
    tail: list[str] = []
    for word in reversed(words):
        if len(" ".join([word, *tail])) > overlap_chars:
            break
        tail.insert(0, word)
    return tail


def chunk_pages(
    pages: list[tuple[int, str]], *, max_chars: int = 900, overlap_chars: int = 120
) -> list[TextChunk]:
    if max_chars < 16 or overlap_chars < 0 or overlap_chars >= max_chars // 2:
        raise ValueError("Invalid chunk size or overlap")
    chunks: list[TextChunk] = []

    for page_number, page_text in pages:
        if page_number < 1:
            raise ValueError("Page numbers are one-based")
        current: list[str] = []

        def flush() -> None:
            if not current:
                return
            original = " ".join(current)
            chunks.append(
                TextChunk(
                    ordinal=len(chunks),
                    page_number=page_number,
                    original_text=original,
                    normalized_text=normalize_arabic(original),
                )
            )

        for paragraph in _sections(page_text):
            words = _words(paragraph, max_chars)
            for word in words:
                candidate = len(" ".join([*current, word]))
                if candidate > max_chars and current:
                    flush()
                    current = _overlap(current, overlap_chars)
                    while current and len(" ".join([*current, word])) > max_chars:
                        current.pop(0)
                current.append(word)
            # Preserve paragraph boundaries as chunk boundaries when the next paragraph
            # would exceed the limit; the blank line is not part of searchable text.
        flush()

    return chunks
