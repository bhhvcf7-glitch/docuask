from pathlib import Path


class OCRUnavailable(RuntimeError):
    pass


def ocr_page(path: Path, page_index: int, *, dpi: int = 180) -> str:
    try:
        import pypdfium2
        import pytesseract
    except ImportError as exc:
        raise OCRUnavailable("OCR Python dependencies are not installed") from exc

    try:
        languages = set(pytesseract.get_languages(config=""))
    except (OSError, pytesseract.TesseractNotFoundError) as exc:
        raise OCRUnavailable("Tesseract is not installed") from exc
    if not {"ara", "eng"}.issubset(languages):
        raise OCRUnavailable("Tesseract language packs ara and eng are required")

    pdf = pypdfium2.PdfDocument(str(path))
    try:
        page = pdf[page_index]
        try:
            bitmap = page.render(scale=dpi / 72)
            try:
                image = bitmap.to_pil()
                try:
                    return pytesseract.image_to_string(image, lang="ara+eng").strip()
                finally:
                    image.close()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        pdf.close()
