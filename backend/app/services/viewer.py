from pathlib import Path

import pdfplumber

from app.ingestion.text import normalize_arabic


def geometry(page, passage: str) -> list[dict]:
    # Match the complete normalized chunk in actual PDF words; never guess a box.
    words = page.extract_words()
    target = " ".join(normalize_arabic(passage).split())
    if not target:
        return []
    normalized = [normalize_arabic(word["text"]) for word in words]
    matches = []
    for start in range(len(words)):
        if not target.startswith(normalized[start]):
            continue
        candidate = ""
        for end in range(start, len(words)):
            candidate = (candidate + " " + normalized[end]).strip()
            if candidate == target:
                matches.append(words[start:end + 1])
                break
            if not target.startswith(candidate):
                break
    if len(matches) != 1:
        return []
    left, top, _, _ = page.bbox
    return [
        {"x": (word["x0"] - left) / page.width,
         "y": (word["top"] - top) / page.height,
         "w": (word["x1"] - word["x0"]) / page.width,
         "h": (word["bottom"] - word["top"]) / page.height}
        for word in matches[0]
    ]


def render_page(path: Path, number: int, passage: str | None) -> dict:
    import base64
    from io import BytesIO

    with pdfplumber.open(path) as pdf:
        if not 1 <= number <= len(pdf.pages):
            raise IndexError("Page not found")
        page = pdf.pages[number - 1]
        # Use the same page coordinate system for raster and word rectangles.
        resolution = min(144, 1600 * 72 / max(page.width, page.height))
        output = BytesIO()
        page.to_image(resolution=resolution, force_mediabox=True).original.save(
            output, format="PNG"
        )
        return {
            "page": number, "page_count": len(pdf.pages),
            "image": base64.b64encode(output.getvalue()).decode("ascii"),
            "boxes": geometry(page, passage) if passage else [],
        }
