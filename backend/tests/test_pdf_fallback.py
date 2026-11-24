from pathlib import Path
from unittest.mock import Mock

import pytest

from app.ingestion import pdf
from app.ingestion.quality import inspect_arabic

FIXTURES = Path(__file__).parent / "fixtures" / "arabic"


@pytest.mark.parametrize(
    ("filename", "phrase"),
    [
        ("jspdf_arabic.pdf", "إذا لم تستح فاصنع ما شئت"),
        ("pdfjs_arabic_cid.pdf", "انواع الخطوط العربية"),
        ("tabula_arabic.pdf", "اسمي سلطان"),
    ],
)
def test_pdfium_recovers_reference_phrase_and_page_number(
    filename: str, phrase: str
) -> None:
    pages = pdf.extract_pages(FIXTURES / filename)
    assert [number for number, _ in pages] == [1]
    assert phrase in pages[0][1]
    assert not inspect_arabic(pages[0][1]).unreliable


def test_no_fallback_when_pdfium_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    called = Mock(side_effect=AssertionError("pypdfium2 should not be called"))
    monkeypatch.setattr(pdf, "pdfium_page", called)
    with pytest.raises(pdf.ExtractionError):
        pdf.extract_pages(FIXTURES / "jspdf_arabic.pdf", pdfium_fallback=False)
    called.assert_not_called()


def test_bad_pdfium_does_not_replace_damaged_original(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf, "pdfium_page", lambda *_: "ةيبرعلا ةغللا طوطخلا عاونا")
    with pytest.raises(pdf.ExtractionError, match="unreliable on page 1"):
        pdf.extract_pages(FIXTURES / "jspdf_arabic.pdf")


def test_ocr_is_opt_in_and_can_recover_unreadable_page(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf, "pdfium_page", lambda *_: "")
    called = Mock(return_value="اللغة العربية سليمة في هذه الصفحة")
    monkeypatch.setattr(pdf, "ocr_page", called)
    with pytest.raises(pdf.ExtractionError):
        pdf.extract_pages(FIXTURES / "jspdf_arabic.pdf", ocr_enabled=False)
    called.assert_not_called()
    assert pdf.extract_pages(
        FIXTURES / "jspdf_arabic.pdf", ocr_enabled=True
    ) == [(1, "اللغة العربية سليمة في هذه الصفحة")]
    called.assert_called_once()


def test_missing_ocr_language_packages_are_reported(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ingestion.ocr import OCRUnavailable

    def missing(*_args):
        raise OCRUnavailable("Tesseract language packs ara and eng are required")

    monkeypatch.setattr(pdf, "pdfium_page", lambda *_: "")
    monkeypatch.setattr(pdf, "ocr_page", missing)
    with pytest.raises(pdf.ExtractionError, match="ara and eng"):
        pdf.extract_pages(FIXTURES / "jspdf_arabic.pdf", ocr_enabled=True)


def test_technical_reversed_words_are_detected() -> None:
    text = "ةكبشلا تانايبلا ماظنلا ليغشتلا"
    assert "suspected_reversed_words" in inspect_arabic(text).issues
    assert not inspect_arabic(
        "تشغيل النظام ومعالجة البيانات عبر الشبكة في مركز المعلومات"
    ).unreliable


def test_short_valid_arabic_and_mixed_english_remain_allowed() -> None:
    samples = [
        "اجهزة الاستشعار تعمل في المحطة الجديدة",
        "API 2026: إدارة البيانات وشبكة الاتصالات",
        "التشغيل والصيانة يتبعان تعليمات القسم",
    ]
    assert all(not inspect_arabic(text).unreliable for text in samples)


def test_ocr_real_engine_is_optional_when_unavailable() -> None:
    import importlib.util
    import shutil

    if not shutil.which("tesseract") or importlib.util.find_spec("pytesseract") is None:
        pytest.skip("Tesseract with Arabic and English language packs not installed")
    import pytesseract

    if not {"ara", "eng"}.issubset(set(pytesseract.get_languages(config=""))):
        pytest.skip("Tesseract ara+eng not installed")
    from app.ingestion.ocr import ocr_page

    assert isinstance(ocr_page(FIXTURES / "jspdf_arabic.pdf", 0), str)
