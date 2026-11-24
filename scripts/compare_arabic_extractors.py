import argparse
import json
from importlib import metadata
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from app.ingestion.quality import inspect_arabic
from app.ingestion.text import normalize_arabic

FIXTURES = Path(__file__).resolve().parents[1] / "backend/tests/fixtures/arabic"
ANCHORS = {
    "jspdf_arabic.pdf": "إذا لم تستح فاصنع ما شئت",
    "pdfjs_arabic_cid.pdf": "انواع الخطوط العربية",
    "tabula_arabic.pdf": "اسمي سلطان",
}
EXTRACTORS = ("pdfplumber", "pypdfium2", "pymupdf", "pypdf")


def pdfplumber_pages(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [(page.extract_text(layout=False) or "") for page in pdf.pages]


def pdfium_pages(path: Path) -> list[str]:
    import pypdfium2

    document = pypdfium2.PdfDocument(str(path))
    try:
        pages = []
        for index in range(len(document)):
            page = document[index]
            try:
                text_page = page.get_textpage()
                try:
                    pages.append(text_page.get_text_range())
                finally:
                    text_page.close()
            finally:
                page.close()
        return pages
    finally:
        document.close()


def pymupdf_pages(path: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(path) as pdf:
        return [page.get_text("text", sort=False) for page in pdf]


def pypdf_pages(path: Path) -> list[str]:
    return [(page.extract_text(extraction_mode="plain") or "") for page in PdfReader(path).pages]


def extract_candidate(path: Path, extractor: str) -> list[str]:
    methods = {
        "pdfplumber": pdfplumber_pages,
        "pypdfium2": pdfium_pages,
        "pymupdf": pymupdf_pages,
        "pypdf": pypdf_pages,
    }
    return methods[extractor](path)


def analyze(text: str, anchor: str | None) -> dict:
    quality = inspect_arabic(text)
    normalized = normalize_arabic(text)
    # A matched reference phrase is evidence of one logical-order span, not page-wide correctness.
    anchor_found = (
        normalize_arabic(anchor).casefold() in normalized.casefold()
        if anchor is not None else None
    )
    return {
        "characters": len(text),
        "issues": list(quality.issues),
        "inspector_rejects": quality.unreliable,
        "logical_anchor_found": anchor_found,
        "logical_order_assessment": (
            "reference_span_found" if anchor_found
            else "reference_span_missing" if anchor is not None
            else "manual_review_required"
        ),
        "sample": text[:240].replace("\n", " "),
        "raw_sample": text[:240],
        "line_samples": text[:240].splitlines(),
    }


def compare(paths: list[Path]) -> dict:
    versions = {}
    for name, package in (
        ("pdfplumber", "pdfplumber"),
        ("pypdfium2", "pypdfium2"),
        ("pymupdf", "PyMuPDF"),
        ("pypdf", "pypdf"),
    ):
        try:
            versions[name] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[name] = None

    rows = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        anchor = ANCHORS.get(path.name) if path.parent.resolve() == FIXTURES.resolve() else None
        for extractor in EXTRACTORS:
            entry = {
                "file": str(path),
                "extractor": extractor,
                "reference": anchor,
            }
            try:
                pages = extract_candidate(path, extractor)
            except (ImportError, OSError, RuntimeError, ValueError) as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["pages"] = []
            else:
                entry["error"] = None
                entry["pages"] = [
                    {"page": number, **analyze(text, anchor if number == 1 else None)}
                    for number, text in enumerate(pages, start=1)
                ]
            rows.append(entry)
    return {
        "schema_version": 2,
        "extractor_versions": versions,
        "anchor_scope": "Known phrase on the first page of each upstream fixture only",
        "rows": rows,
    }


def markdown_table(report: dict) -> str:
    lines = [
        "| PDF | Extractor | Page | Chars | Inspector issues | Rejected | Logical-order evidence | Sample |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        if row["error"]:
            cells = [Path(row["file"]).name, row["extractor"], "-", "-", row["error"], "-", "-", "-"]
            lines.append("| " + " | ".join(escape(cell) for cell in cells) + " |")
            continue
        for page in row["pages"]:
            cells = [
                Path(row["file"]).name, row["extractor"], str(page["page"]),
                str(page["characters"]), ", ".join(page["issues"]) or "none",
                str(page["inspector_rejects"]), page["logical_order_assessment"],
                page["sample"][:110],
            ]
            lines.append("| " + " | ".join(escape(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Arabic PDF text extractors")
    parser.add_argument("--pdf", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=Path("docs/extraction/comparison.local.json"))
    parser.add_argument("--markdown", type=Path, default=Path("docs/extraction/comparison.local.md"))
    args = parser.parse_args()
    paths = sorted(FIXTURES.glob("*.pdf")) + args.pdf
    report = compare(paths)
    table = markdown_table(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(table, encoding="utf-8")
    print(table)
    print(f"Saved {args.output} and {args.markdown}")


if __name__ == "__main__":
    main()
