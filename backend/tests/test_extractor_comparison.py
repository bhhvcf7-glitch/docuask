from scripts.compare_arabic_extractors import (
    ANCHORS,
    FIXTURES,
    analyze,
    compare,
    markdown_table,
    pypdf_pages,
)

from app.ingestion.quality import inspect_arabic


def test_comparison_reports_inspector_and_reference_independently() -> None:
    text = "انواع الخطوط العربية"
    reading = analyze(text, "انواع الخطوط العربية")
    assert reading["logical_anchor_found"]
    assert not reading["inspector_rejects"]
    assert reading["logical_order_assessment"] == "reference_span_found"

    damaged = analyze("ةيبرعلا طوطخلا عاونا", "انواع الخطوط العربية")
    assert not damaged["logical_anchor_found"]
    assert damaged["logical_order_assessment"] == "reference_span_missing"


def test_unknown_additional_pdf_requires_manual_review() -> None:
    reading = analyze("هذه عينة عربية سليمة", None)
    assert not reading["inspector_rejects"]
    assert reading["logical_anchor_found"] is None
    assert reading["logical_order_assessment"] == "manual_review_required"


def test_pypdf_extracts_all_upstream_fixtures() -> None:
    for filename in ANCHORS:
        pages = pypdf_pages(FIXTURES / filename)
        assert len(pages) == 1
        assert isinstance(pages[0], str)


def test_comparison_records_errors_without_attributing_quality() -> None:
    report = compare([FIXTURES / "jspdf_arabic.pdf"])
    assert len(report["rows"]) == 4
    assert {row["extractor"] for row in report["rows"]} == {
        "pdfplumber", "pypdfium2", "pymupdf", "pypdf"
    }
    for row in report["rows"]:
        if row["error"]:
            assert row["pages"] == []
        else:
            assert row["pages"]
            assert "inspector_rejects" in row["pages"][0]
    table = markdown_table(report)
    assert "| PDF | Extractor | Page |" in table
    assert "jspdf_arabic.pdf" in table


def test_existing_inspector_still_rejects_known_bad_extraction() -> None:
    assert inspect_arabic("ةيبرعلا ةغللا طوطخلا عاونا").unreliable
