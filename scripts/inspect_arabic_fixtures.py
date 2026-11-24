from pathlib import Path
import unicodedata

import pdfplumber

ROOT = Path(__file__).resolve().parents[1] / "backend/tests/fixtures/arabic"

for path in sorted(ROOT.glob("*.pdf")):
    print(f"FILE {path.name} ({path.stat().st_size} bytes)")
    with pdfplumber.open(path) as pdf:
        print(f"PAGES {len(pdf.pages)}")
        for page_no, page in enumerate(pdf.pages[:3], 1):
            text = page.extract_text(layout=False) or ""
            arabic = sum("\u0600" <= char <= "\u06ff" for char in text)
            presentation = sum(
                "\ufb50" <= char <= "\ufdff" or "\ufe70" <= char <= "\ufeff"
                for char in text
            )
            replacement = text.count("\ufffd")
            print(
                f"PAGE {page_no} length={len(text)} arabic={arabic} "
                f"presentation={presentation} replacement={replacement} "
                f"chars={len(page.chars)}"
            )
            print(f"EXCERPT {text[:350]!r}")
            print(
                "UNICODE",
                [(f"U+{ord(c):04X}", unicodedata.name(c, "?"))
                 for c in text if "\ufb50" <= c <= "\ufdff" or "\ufe70" <= c <= "\ufeff][:8],
            )
