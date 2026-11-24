import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.qa import QuestionRequest
from app.services.qa import CitationFilter, answer_events, make_messages, refusal

HIT = {
    "chunk_id": uuid4(), "document_id": uuid4(),
    "filename": "report.pdf", "page_number": 3,
    "text": "Revenue grew.", "score": 0.9,
}
SECOND = {
    "chunk_id": uuid4(), "document_id": uuid4(),
    "filename": "another.pdf", "page_number": 7,
    "text": "Another passage.", "score": 0.85,
}


class FakeProvider:
    def __init__(self, tokens):
        self.tokens = tokens
        self.closed = False

    async def stream(self, messages):
        try:
            for token in self.tokens:
                yield token
        finally:
            self.closed = True


async def search(*args, **kwargs):
    return [HIT]


async def empty(*args, **kwargs):
    return []


def unpack(parts):
    return [(p.splitlines()[0][7:], json.loads(p.splitlines()[1][6:])) for p in parts]


def test_prompt_uses_short_numbers_not_uuids() -> None:
    prompt = make_messages("What?", [HIT, SECOND])[0]["content"]
    assert "[1]" in prompt and "[2]" in prompt
    assert str(HIT["chunk_id"]) not in prompt
    assert str(SECOND["chunk_id"]) not in prompt


def test_filter_keeps_original_source_numbers_and_ownership() -> None:
    citations = CitationFilter([HIT, SECOND])
    assert citations.push("Second [") == "Second "
    assert citations.push("2], then [") == "[2], then "
    assert citations.push("9] and [1] and [2].") == " and [1] and [2]."
    assert citations.sources() == [
        {
            "number": 2, "chunk_id": str(SECOND["chunk_id"]),
            "document_id": str(SECOND["document_id"]),
            "filename": "another.pdf", "page_number": 7,
            "text": "Another passage.",
        },
        {
            "number": 1, "chunk_id": str(HIT["chunk_id"]),
            "document_id": str(HIT["document_id"]),
            "filename": "report.pdf", "page_number": 3,
            "text": "Revenue grew.",
        },
    ]


@pytest.mark.asyncio
async def test_answer_stream_only_cites_retrieved_numbers() -> None:
    provider = FakeProvider(["Revenue [", "1]"])
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="Revenue?", limit=5,
        settings=Settings(_env_file=None), provider=provider, search=search,
    )])
    visible = "".join(payload["text"] for kind, payload in records if kind == "token")
    assert "[1]" in visible and "[99]" not in visible
    assert [item["chunk_id"] for item in records[-2][1]["sources"]] == [
        str(HIT["chunk_id"])
    ]
    assert records[-2][1]["sources"][0]["page_number"] == 3
    assert records[-1][0] == "done"
    assert provider.closed


@pytest.mark.asyncio
async def test_low_score_refuses_without_invoking_provider() -> None:
    provider = FakeProvider(["no"])
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="ما النتيجة؟", limit=5,
        settings=Settings(_env_file=None, qa_min_score=0.95),
        provider=provider, search=search,
    )])
    assert records == [
        ("refusal", {"answer": refusal("ما النتيجة؟"), "citations": []}),
        ("done", {}),
    ]
    assert not provider.closed


@pytest.mark.asyncio
async def test_empty_retrieval_refuses() -> None:
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="What?", limit=5,
        settings=Settings(_env_file=None),
        provider=FakeProvider([]), search=empty,
    )])
    assert records[0][0] == "refusal"


@pytest.mark.asyncio
async def test_disconnect_closes_provider() -> None:
    provider = FakeProvider(["a", "b"])

    async def disconnected():
        return True

    parts = [p async for p in answer_events(
        None, user_id=uuid4(), question="What?", limit=5,
        settings=Settings(_env_file=None), provider=provider,
        disconnect=disconnected, search=search,
    )]
    assert parts == [] and provider.closed


@pytest.mark.asyncio
async def test_closing_sse_generator_closes_llm_stream() -> None:
    provider = FakeProvider(["first [1]", "\nsecond [1]"])
    stream = answer_events(
        None, user_id=uuid4(), question="What?", limit=5,
        settings=Settings(_env_file=None), provider=provider, search=search,
    )
    assert (await anext(stream)).startswith("event: token")
    await stream.aclose()
    assert provider.closed


def test_invalid_citations_do_not_leak() -> None:
    citation = CitationFilter([HIT])
    assert citation.push("hello [") == "hello "
    assert citation.push("42] end") == " end"
    assert citation.push("[source:abc]") == ""
    assert citation.push("[unfinished") == ""
    assert citation.finish() == ""
    assert citation.sources() == []


def test_numeric_references_outside_retrieval_are_dropped() -> None:
    citations = CitationFilter([HIT])
    assert citations.push("[9999] [01] [0] [1]") == "   [1]"
    assert [source["number"] for source in citations.sources()] == [1]


def test_citation_filter_preserves_non_citation_brackets() -> None:
    filter_ = CitationFilter([HIT])
    assert filter_.push("A [note] and [1]") == "A [note] and [1]"
    assert filter_.sources()[0]["number"] == 1


def test_invalid_question_is_rejected() -> None:
    with pytest.raises(ValidationError):
        QuestionRequest(question="")
    with pytest.raises(ValidationError):
        QuestionRequest(question="valid", limit=11)


@pytest.mark.asyncio
async def test_uncited_model_answer_is_refused() -> None:
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="What?", limit=5,
        settings=Settings(_env_file=None),
        provider=FakeProvider(["unverified statement"]), search=search,
    )])
    assert records[0][0] == "refusal"
    assert all(kind != "token" for kind, _ in records)


@pytest.mark.parametrize("tokens", [
    ["Revenue grew [1]. Unsupported statement."],
    ["Revenue grew [1] and invented [99]"],
    ["Revenue grew [1]", "\nUnsupported claim"],
    ["[1]"],
    ["Revenue grew [1] [unfinished"],
    ["Revenue grew [1] [" + "9" * 5000 + "]"],
])
@pytest.mark.asyncio
async def test_invalid_answer_is_never_released(tokens):
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="Revenue?", limit=5,
        settings=Settings(_env_file=None), provider=FakeProvider(tokens), search=search,
    )])
    assert [kind for kind, _ in records] == ["refusal", "done"]


@pytest.mark.asyncio
async def test_bilingual_cited_claims_are_released():
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="ما النتيجة؟", limit=5,
        settings=Settings(_env_file=None),
        provider=FakeProvider(["ارتفعت الإيرادات [", "1]."]), search=search,
    )])
    assert [kind for kind, _ in records] == ["token", "citations", "done"]


@pytest.mark.asyncio
async def test_raw_answer_limit_counts_invalid_references():
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="Revenue?", limit=5,
        settings=Settings(_env_file=None, qa_max_answer_chars=100),
        provider=FakeProvider(["[99]" * 30]), search=search,
    )])
    assert [kind for kind, _ in records] == ["error"]
