import pdfplumber
from reportlab.pdfgen import canvas

from app.services.viewer import geometry, render_page


def test_real_pdf_geometry_and_missing_text(tmp_path):
    path = tmp_path / "sample.pdf"
    pdf = canvas.Canvas(str(path), pagesize=(300, 400))
    pdf.drawString(30, 350, "Unique evidence phrase")
    pdf.showPage()
    pdf.save()
    with pdfplumber.open(path) as source:
        boxes = geometry(source.pages[0], "Unique evidence phrase")
        assert len(boxes) == 3
        assert abs(boxes[0]["x"] - 0.1) < 0.01
        assert geometry(source.pages[0], "not present") == []
    result = render_page(path, 1, "Unique evidence phrase")
    assert result["page_count"] == 1
    assert result["image"].startswith("iVBOR")
    assert result["boxes"] == boxes
