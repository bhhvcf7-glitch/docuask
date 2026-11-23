import pytest

from app.ingestion.chunking import chunk_pages
from app.ingestion.text import normalize_arabic


def test_arabic_normalization_handles_diacritics_alef_yaa_and_digits() -> None:
    source = "آمِنْ ـ أَكَلَ إِلَى ٱلْبَيْتِ ١٢٣ ۴۵۶"
    assert normalize_arabic(source) == "امن  اكل الي البيت 123 456"


def test_normalization_does_not_guess_reversed_pdf_text() -> None:
    reversed_text = "ةيبرعلا ةغللا"
    assert normalize_arabic(reversed_text) == reversed_text


def test_chunks_keep_original_text_and_page_number() -> None:
    chunks = chunk_pages([(2, "أَهْلًا ١٢٣"), (4, "English text")])
    assert [(chunk.page_number, chunk.ordinal) for chunk in chunks] == [(2, 0), (4, 1)]
    assert chunks[0].original_text == "أَهْلًا ١٢٣"
    assert chunks[0].normalized_text == "اهلا 123"
    assert chunks[1].original_text == "English text"


def test_long_page_has_bounded_overlapping_chunks() -> None:
    source = " ".join(f"word{number}" for number in range(80))
    chunks = chunk_pages([(1, source)], max_chars=80, overlap_chars=20)
    assert len(chunks) > 3
    assert all(len(chunk.original_text) <= 80 for chunk in chunks)
    assert all(chunk.page_number == 1 for chunk in chunks)
    for before, after in zip(chunks, chunks[1:]):
        assert set(before.original_text.split()) & set(after.original_text.split())


def test_paragraphs_and_page_boundaries_do_not_create_empty_chunks() -> None:
    chunks = chunk_pages([(1, "First paragraph\n\nSecond paragraph"), (2, "  ")])
    assert len(chunks) == 1
    assert chunks[0].original_text == "First paragraph Second paragraph"


def test_bad_chunk_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_pages([(1, "hello")], max_chars=20, overlap_chars=10)
    with pytest.raises(ValueError):
        chunk_pages([(0, "hello")])
