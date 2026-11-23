import inspect

from app.api.routes.documents import upload_document


def test_upload_endpoint_accepts_background_tasks() -> None:
    assert "background_tasks" in inspect.signature(upload_document).parameters
