import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.search import SearchRequest


def test_search_requires_bearer_token() -> None:
    with TestClient(app) as client:
        assert client.post("/search", json={"question": "Hello"}).status_code == 401


@pytest.mark.parametrize("question", ["", "a" * 2001])
def test_invalid_search_question_is_rejected(question: str) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(question=question)


def test_search_limit_is_bounded() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(question="Hello", limit=21)
