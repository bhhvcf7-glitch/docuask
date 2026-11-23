import pytest

from app.ingestion.chunking import chunk_pages


def test_arabic_sentence_boundaries_take_priority_over_word_splits() -> None:
    text = "سؤال أول؟ إجابة مختصرة؛ توضيح مهم، جملة أخيرة."
    chunks = chunk_pages([(3, text)], max_chars=25, overlap_chars=0)
    assert [chunk.original_text for chunk in chunks] == [
        "سؤال أول؟ إجابة مختصرة؛",
        "توضيح مهم، جملة أخيرة.",
    ]
    assert [chunk.page_number for chunk in chunks] == [3, 3]
    assert [chunk.ordinal for chunk in chunks] == [0, 1]


def test_arabic_punctuation_without_spaces_is_a_split_point() -> None:
    chunks = chunk_pages(
        [(1, "أولًا،ثانيًا؛ثالثًا؟رابعًا.")], max_chars=16, overlap_chars=0
    )
    assert [chunk.original_text for chunk in chunks] == [
        "أولًا، ثانيًا؛",
        "ثالثًا؟ رابعًا.",
    ]


def test_english_sentences_precede_word_level_fallback() -> None:
    chunks = chunk_pages(
        [(1, "First sentence ends here. Next sentence continues. Last sentence.")],
        max_chars=32, overlap_chars=0,
    )
    assert [chunk.original_text for chunk in chunks] == [
        "First sentence ends here.",
        "Next sentence continues.",
        "Last sentence.",
    ]


def test_english_comma_semicolon_and_colon_are_preferred_boundaries() -> None:
    chunks = chunk_pages(
        [(1, "Part one, part two; part three: last item.")],
        max_chars=23, overlap_chars=0,
    )
    assert [chunk.original_text for chunk in chunks] == [
        "Part one, part two;",
        "part three: last item.",
    ]


def test_oversized_sentence_uses_words_and_retains_overlap() -> None:
    text = " ".join("alpha beta gamma delta epsilon".split() * 9)
    chunks = chunk_pages([(2, text)], max_chars=45, overlap_chars=16)
    assert len(chunks) >= 5
    assert all(0 < len(chunk.original_text) <= 45 for chunk in chunks)
    assert all(chunk.page_number == 2 for chunk in chunks)
    for before, after in zip(chunks, chunks[1:], strict=False):
        assert set(before.original_text.split()) & set(after.original_text.split())


def test_overlap_stays_inside_paragraph_and_page() -> None:
    chunks = chunk_pages(
        [
            (2, "Alpha beta gamma delta epsilon zeta eta theta.\n\nSecond paragraph."),
            (5, "Different page starts here."),
        ],
        max_chars=33, overlap_chars=10,
    )
    assert chunks[-2].original_text == "Second paragraph."
    assert chunks[-1].original_text == "Different page starts here."
    assert [(chunk.page_number, chunk.ordinal) for chunk in chunks] == [
        (2, number) for number in range(len(chunks) - 1)
    ] + [(5, len(chunks) - 1)]


def test_single_long_word_is_bounded_without_infinite_loop() -> None:
    chunks = chunk_pages([(1, "س" * 97)], max_chars=20, overlap_chars=6)
    assert [len(chunk.original_text) for chunk in chunks] == [20, 20, 20, 20, 17]
    assert all(chunk.normalized_text == chunk.original_text for chunk in chunks)


@pytest.mark.parametrize("page", [0, -5])
def test_page_number_must_be_positive(page: int) -> None:
    with pytest.raises(ValueError, match="one-based"):
        chunk_pages([(page, "Text")])
