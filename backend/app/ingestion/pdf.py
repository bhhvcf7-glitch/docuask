from pathlib import Path

import pdfplumber
import structlog
from pdfminer.pdfexceptions import PDFException
from pdfplumber.utils.exceptions import PdfminerException

from app.ingestion.ocr import OCRUnavailable, ocr_page
from app.ingestion.quality import inspect_arabic

log = structlog.get_logger(__name__)


class ExtractionError(ValueError):
    pass


def pdfium_page(path: Path, page_index: int) -> str:
    import pypdfium2

    pdf = pypdfium2.PdfDocument(str(path))
    try:
        page = pdf[page_index]
        try:
            textpage = page.get_textpage()
            try:
                return textpage.get_text_range().strip()
            finally:
                textpage.close()
        finally:
            page.close()
    finally:
        pdf.close()


def extract_pages(
    path: Path, *, max_pages: int = 200,
    pdfium_fallback: bool = True, ocr_enabled: bool = False,
) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > max_pages:
                raise ExtractionError("PDF exceeds page limit")
            for page_number, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text(layout=False) or "").strip()
                quality = inspect_arabic(text)
                if quality.issues:
                    log.warning(
                        "pdf_text_quality",
                        page_number=page_number, extractor="pdfplumber",
                        issues=quality.issues,
                    )

                if (not text or quality.unreliable) and pdfium_fallback:
                    try:
                        alternative = pdfium_page(path, page_number - 1)
                    except (ImportError, OSError, RuntimeError, ValueError) as exc:
                        log.warning(
                            "pdfium_extraction_failed",
                            page_number=page_number, error_type=type(exc).__name__,
                        )
                    else:
                        checked = inspect_arabic(alternative)
                        if alternative and not checked.unreliable:
                            text, quality = alternative, checked
                            log.info(
                                "pdf_extraction_fallback",
                                page_number=page_number, extractor="pypdfium2",
                            )

                if (not text or quality.unreliable) and ocr_enabled:
                    try:
                        alternative = ocr_page(path, page_number - 1)
                    except OCRUnavailable as exc:
                        raise ExtractionError(str(exc)) from exc
                    except (OSError, RuntimeError, ValueError) as exc:
                        raise ExtractionError("OCR failed on page " + str(page_number)) from exc
                    checked = inspect_arabic(alternative)
                    if alternative and not checked.unreliable:
                        text, quality = alternative, checked
                        log.info("pdf_extraction_fallback", page_number=page_number, extractor="tesseract")

                if quality.unreliable:
                    raise ExtractionError(
                        f"PDF text extraction appears unreliable on page {page_number}; "
                        "a different PDF or OCR is needed"
                    )
                if text:
                    pages.append((page_number, text))
    except (PDFException, PdfminerException, OSError) as exc:
        raise ExtractionError("Could not extract text from PDF") from exc

    if not pages:
        raise ExtractionError("PDF has no extractable text; OCR is not available yet")
    return pages
