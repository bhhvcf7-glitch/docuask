from pathlib import Path

import pdfplumber
import pytest

from app.ingestion.pdf import ExtractionError, extract_pages
from app.ingestion.quality import inspect_arabic
from app.ingestion.text import normalize_arabic

FIXTURES = Path(__file__).parent / "fixtures" / "arabic"


@pytest.mark.parametrize(
    "filename",
    ["jspdf_arabic.pdf", "pdfjs_arabic_cid.pdf", "tabula_arabic.pdf"],
)
def test_public_arabic_pdfs_show_real_extraction_damage(filename: str) -> None:
    path = FIXTURES / filename
    assert path.read_bytes().startswith(b"%PDF-")
    with pdfplumber.open(path) as pdf:
        assert len(pdf.pages) == 1
        text = pdf.pages[0].extract_text() or ""
    quality = inspect_arabic(text)
    assert "presentation_forms" in quality.issues
    assert "suspected_reversed_words" in quality.issues
    assert quality.unreliable
    with pytest.raises(ExtractionError, match="unreliable on page 1"):
        extract_pages(path)


def test_reversed_words_are_detected_but_never_reordered() -> None:
    damaged = "ةيبرعلا ةغللا طوطخلا عاونا"
    quality = inspect_arabic(damaged)
    assert quality.issues == ("suspected_reversed_words",)
    assert quality.unreliable
    assert normalize_arabic(damaged) == damaged


def test_disconnected_letters_require_many_isolated_tokens() -> None:
    damaged = "ا ل ع ر ب ي ة م د ر س ة"
    quality = inspect_arabic(damaged)
    assert quality.issues == ("disconnected_letters",)
    assert quality.unreliable
    assert not inspect_arabic("أ ب ت").issues


def test_cid_placeholders_and_replacement_chars_are_detected() -> None:
    assert inspect_arabic("(cid:20)(cid:21)(cid:22)").unreliable
    assert inspect_arabic("\ufffd\ufffd\ufffd").issues == ("unmapped_glyphs",)


def test_ligatures_fold_only_in_normalized_text() -> None:
    source = "ﻻ ﷲ ﺔﻴﺑﺮﻌﻟا ①"
    assert normalize_arabic(source) == "لا الله ةيبرعلا ①"
    quality = inspect_arabic(source)
    assert quality.issues == ("presentation_forms",)
    assert not quality.unreliable


def test_normal_arabic_is_not_marked_reversed_or_fragmented() -> None:
    source = "اللغة العربية جميلة، هذه المعلومات عن الخطوط العربية."
    quality = inspect_arabic(source)
    assert not quality.issues
    assert not quality.unreliable


def test_mixed_english_and_arabic_short_text_is_not_rejected() -> None:
    source = "Report 2026: الإيرادات أعلى من السنة الماضية."
    assert not inspect_arabic(source).unreliable
