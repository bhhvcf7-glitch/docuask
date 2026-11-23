from pathlib import Path

import pdfplumber
from pdfminer.pdfexceptions import PDFException
from pdfplumber.utils.exceptions import PdfminerException


class ExtractionError(ValueError):
    pass


def extract_pages(path: Path, *, max_pages: int = 200) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > max_pages:
                raise ExtractionError("PDF exceeds page limit")
            for page_number, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text(layout=False) or "").strip()
                if text:
                    pages.append((page_number, text))
    except (PDFException, PdfminerException, OSError) as exc:
        raise ExtractionError("Could not extract text from PDF") from exc

    if not pages:
        raise ExtractionError("PDF has no extractable text; OCR is not available yet")
    return pages
