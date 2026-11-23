import argparse
import asyncio
import io
import json
import secrets
from uuid import uuid4

import httpx
from reportlab.pdfgen import canvas


def sample_pdf() -> bytes:
    output = io.BytesIO()
    document = canvas.Canvas(output)
    document.drawString(45, 750, "The DocuAsk test report lists total revenue as 250.")
    document.showPage()
    document.save()
    return output.getvalue()


async def main(base_url: str) -> None:
    email = f"smoke-{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(20)

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        registration = await client.post(
            "/auth/register", json={"email": email, "password": password}
        )
        registration.raise_for_status()

        login = await client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        uploaded = await client.post(
            "/documents",
            files={"file": ("smoke.pdf", sample_pdf(), "application/pdf")},
        )
        uploaded.raise_for_status()
        document_id = uploaded.json()["id"]

        for attempt in range(120):
            status = await client.get(f"/documents/{document_id}")
            status.raise_for_status()
            state = status.json()["status"]
            if state in ("ready", "failed"):
                break
            await asyncio.sleep(2)
        else:
            raise RuntimeError("Ingestion never completed")

        if state != "ready":
            raise RuntimeError(f"Ingestion ended with status {state}")

        search = await client.post(
            "/search", json={"question": "What is the revenue?", "limit": 5}
        )
        search.raise_for_status()
        passages = search.json()
        assert passages and passages[0]["page_number"] == 1
        print("Retrieval: passed (page 1)")

        seen = set()
        citation_ids = set()
        async with client.stream(
            "POST", "/qa/ask", json={"question": "What was the revenue?"}
        ) as response:
            response.raise_for_status()
            event_name = None
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and event_name:
                    payload = json.loads(line[5:].strip())
                    seen.add(event_name)
                    if event_name == "citations":
                        citation_ids.update(source["chunk_id"] for source in payload["sources"])
                    if event_name == "error":
                        raise RuntimeError(f"QA error: {payload}")
                    if event_name == "refusal":
                        raise RuntimeError(f"QA refusal: {payload}")
                    event_name = None

        valid_ids = {passage["chunk_id"] for passage in passages}
        assert "token" in seen and "citations" in seen and "done" in seen, seen
        assert citation_ids and citation_ids.issubset(valid_ids)
        print("SSE answer and validated page citations: passed")
        print(f"Smoke test passed for document {document_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(main(args.api))
