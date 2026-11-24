# Arabic PDF extractor comparison

The comparison runs on the three unchanged public regression PDFs in
`backend/tests/fixtures/arabic/`: jsPDF's `arabic.pdf`, PDF.js's
`ArabicCIDTrueType.pdf`, and Tabula's `arabic.pdf`. The historical baseline used **pdfplumber** without fallback. The current runtime enables PDFium fallback for empty or inspector-rejected pages; OCR is optional.

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

## Measured baseline on three upstream fixtures

GitHub Actions run [45413080689](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45413080689)
executed the four extractors on 2026-11-24. The table below summarizes
**first-page anchor checks** and the existing quality inspector:

| Extractor | First-page anchor found | Pages rejected by inspector | Observations |
| --- | ---: | ---: | --- |
| pdfplumber | 0/3 | 3/3 | Reversed visual-order phrases in every fixture |
| pypdfium2 | 3/3 | 0/3 | Correct-order reference phrases found in all three |
| PyMuPDF | 2/3 | 0/3 | Presentation forms remained; Tabula anchor was not an exact match |
| pypdf | 1/3 | 0/3 | Reference phrase found only for jsPDF; PDF.js and Tabula appeared visually reordered |

The inspector's pass/reject result is not a correctness score. In particular,
PyMuPDF and pypdf pass the current heuristic on some output where the reference
phrase is absent. The PyMuPDF Tabula sample contains non-breaking spaces and
may be readable despite failing the exact substring check. Read the raw
samples before interpreting that result.

Detailed per-fixture results:

| PDF | pdfplumber | pypdfium2 | PyMuPDF | pypdf |
| --- | --- | --- | --- | --- |
| jsPDF | 24 chars; reversed | 24 chars; anchor found | 25 chars; anchor found | 24 chars; anchor found |
| PDF.js Arabic CID | 79 chars; reversed | 86 chars; anchor found | 80 chars; anchor found | 79 chars; anchor missing |
| Tabula | 138 chars; reversed | 146 chars; anchor found | 154 chars; anchor missing | 150 chars; anchor missing |

All character counts are from extracted text (not visual glyph counts).
The [raw CI report](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45413080689/artifacts/14928833277)
contains actual samples, all issues and the extractor package versions.

**Historical decision:** Retain pdfplumber as the primary extractor and evaluate a narrowly scoped PDFium fallback. The fallback has since been enabled; broader layout validation is still required. The three small fixtures
do not prove page-wide reading-order correctness, nor that fallback improves
retrieval accuracy.

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

## Phase I: reading-order diagnostics

The extractor-comparison job in [run 45485366699](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45485366699/job/138769193847) printed a Tabula PDFium sample beginning with `اسمي سلطان  ً  مرحبا`. This supports the reference-span check but not a conclusion about the visual order of the whole page. The logged sample flattened line breaks. Visual coordinates and a manually transcribed reference are needed to distinguish within-line ordering from between-line ordering. No global line or word reversal is introduced.

The diagnostic report now preserves raw first-240-character excerpts and line samples separately from the existing flattened Markdown sample. These are sensitive for user-provided PDFs: run locally and do not publish private reports. Reference checks remain limited to upstream fixtures. The vocabulary heuristic is not a language model; unfamiliar terminology and ambiguous reversed tokens can escape detection. Tests cover representative technical and mixed-language text, not a measured population-level false-positive rate.
