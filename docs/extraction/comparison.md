# Arabic PDF extractor comparison

The comparison runs on the three unchanged public regression PDFs in
`backend/tests/fixtures/arabic/`: jsPDF's `arabic.pdf`, PDF.js's
`ArabicCIDTrueType.pdf`, and Tabula's `arabic.pdf`. The existing production
extractor remains **pdfplumber**, and no fallback has been enabled.

The script runs four extractors on every page:

- `pdfplumber`, current production behavior
- `pypdfium2`, PDFium text-page extraction
- `PyMuPDF`, MuPDF `get_text("text", sort=False)`
- `pypdf`, pure Python text extraction in plain mode

Each row contains extracted character count, a sample, quality-inspector
issues, its reject decision, and whether a **known first-page reference
phrase** occurs in logical order. The reference phrases are:

| Fixture | Reference phrase |
| --- | --- |
| `jspdf_arabic.pdf` | `إذا لم تستح فاصنع ما شئت` |
| `pdfjs_arabic_cid.pdf` | `انواع الخطوط العربية` |
| `tabula_arabic.pdf` | `اسمي سلطان` |

These anchors are diagnostic checks on short spans, not manually transcribed
full-page ground truth. A matching span is necessary evidence for that span
alone; it is not proof that the entire page has correct logical order. A
missing span can also result from extraction differences and does not prove
that every other part of the page is damaged. Extractor outputs for user-
supplied PDFs have no known reference anchor and are marked
`manual_review_required`, rather than being graded automatically.

## Reproduce on Windows

```powershell
py -3.11 -m pip install -e "./backend[dev,extractor-comparison]"
py -3.11 scripts/compare_arabic_extractors.py
```

To include another PDF:

```powershell
py -3.11 scripts/compare_arabic_extractors.py --pdf "C:\\path\\to\\arabic.pdf"
```

Outputs:

- `docs/extraction/comparison.local.json`: full per-page diagnostics
- `docs/extraction/comparison.local.md`: comparison table

The generated local reports are ignored by Git. A separate GitHub Actions
comparison job publishes its results as the `arabic-extractor-comparison`
artifact. It does not download LLM weights or use OCR.

## Licensing

**PyMuPDF / MuPDF is licensed under AGPL-3.0 or a paid commercial license.**
It is installed only by the optional `extractor-comparison` extra and used
for diagnostics; it is not part of the default runtime or Docker image.
Do not adopt it in a deployed proprietary service without reviewing and
meeting the applicable AGPL obligations or obtaining a commercial license.
See the [official PyMuPDF licensing terms](https://pymupdf.io/licensing).

`pypdfium2` is available under Apache-2.0 or BSD-3-Clause, with PDFium's
BSD-style license and third-party notices. Check shipped notices when
redistributing PDFium binaries; see the [pypdfium2 documentation](https://pypdfium2.readthedocs.io/en/stable/readme.html).

This phase compares extraction behavior. It does not change DocuAsk's
licensing or make a blanket claim that any extractor fixes Arabic PDFs.

## Adoption criteria

A production fallback requires reproducible evidence of better logical
reading order on a representative set of PDFs, not just fewer inspector
warnings or longer text. Review the raw text for multiple pages and types
of Arabic layouts; record false positives, damaged pages, and licensing
constraints. If no extractor reliably recovers these samples, retain
pdfplumber and reject them until a later OCR or reconstruction strategy
is measured.

Scanned PDFs, bidirectional mixed-language runs, and missing ToUnicode
maps are still outside the scope of a guaranteed solution.
