from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.ingestion.pdf import ExtractionError, extract_pages


def write_pdf(path: Path, *, arabic_font: Path | None = None) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(50, 750, "English contract, page one.")
    pdf.showPage()
    if arabic_font:
        pdfmetrics.registerFont(TTFont("DejaVuTest", str(arabic_font)))
        pdf.setFont("DejaVuTest", 14)
        pdf.drawString(50, 750, "لغة عربية ١٢٣")
    else:
        pdf.drawString(50, 750, "Second page.")
    pdf.save()


def test_pdfplumber_keeps_real_page_numbers(tmp_path: Path) -> None:
    path = tmp_path / "pages.pdf"
    write_pdf(path)
    pages = extract_pages(path)
    assert [number for number, _ in pages] == [1, 2]
    assert "English contract" in pages[0][1]
    assert "Second page" in pages[1][1]


def test_pdfplumber_extracts_arabic_glyphs_from_a_real_pdf(tmp_path: Path) -> None:
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.exists():
        pytest.skip("DejaVuSans font not available on this runner")
    path = tmp_path / "bilingual.pdf"
    write_pdf(path, arabic_font=font)
    pages = extract_pages(path)
    assert [number for number, _ in pages] == [1, 2]
    assert any("\u0600" <= char <= "\u06ff" for char in pages[1][1])
    assert "١٢٣" in pages[1][1]


def test_corrupt_pdf_and_page_limit_report_failure(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    with pytest.raises(ExtractionError):
        extract_pages(broken)
    valid = tmp_path / "valid.pdf"
    write_pdf(valid)
    with pytest.raises(ExtractionError, match="page limit"):
        extract_pages(valid, max_pages=1)
