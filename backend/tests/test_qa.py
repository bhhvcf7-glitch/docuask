import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.qa import QuestionRequest
from app.services.qa import CitationFilter, answer_events, refusal

HIT = {
    "chunk_id": uuid4(), "document_id": uuid4(),
    "filename": "report.pdf", "page_number": 3,
    "text": "Revenue grew.", "score": 0.9,
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


@pytest.mark.asyncio
async def test_answer_stream_accepts_only_retrieved_chunk_ids() -> None:
    valid = str(HIT["chunk_id"])
    invalid = str(uuid4())
    provider = FakeProvider(["Revenue [sou", f"rce:{valid}]",
                             f" and [source:{invalid}]"])
    records = unpack([p async for p in answer_events(
        None, user_id=uuid4(), question="Revenue?", limit=5,
        settings=Settings(_env_file=None), provider=provider, search=search,
    )])
    text = "".join(payload["text"] for kind, payload in records if kind == "token")
    assert "[1]" in text and invalid not in text
    assert [s["chunk_id"] for s in records[-2][1]["sources"]] == [valid]
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
    provider = FakeProvider(["first", "second"])
    stream = answer_events(
        None, user_id=uuid4(), question="What?", limit=5,
        settings=Settings(_env_file=None), provider=provider, search=search,
    )
    assert (await anext(stream)).startswith("event: token")
    await stream.aclose()
    assert provider.closed


def test_invalid_citations_do_not_leak() -> None:
    citation = CitationFilter([HIT])
    assert citation.push("hello [source:") == "hello "
    assert citation.push(str(uuid4()) + "] end") == " end"
    assert citation.push("[source:unfinished") == ""
    assert citation.finish() == ""
    assert citation.sources() == []


def test_invalid_question_is_rejected() -> None:
    with pytest.raises(ValidationError):
        QuestionRequest(question="")
    with pytest.raises(ValidationError):
        QuestionRequest(question="valid", limit=11)
