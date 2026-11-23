import inspect

from fastapi.routing import APIRoute

from app.main import app


def test_upload_endpoint_is_configured_with_background_tasks() -> None:
    route = next(
        route for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/documents"
        and "POST" in route.methods
    )
    assert "background_tasks" in inspect.signature(route.endpoint).parameters
