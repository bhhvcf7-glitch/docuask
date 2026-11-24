# Arabic PDF extraction: fallback and optional OCR

The default pipeline tries `pdfplumber` on each page. When a page is empty or
the Arabic quality inspector marks it unreliable, it tries `pypdfium2`.
Only nonempty text passing the same inspector replaces the primary output.
A clean `pdfplumber` page is never replaced. Page numbering is unchanged and
no text is blindly reversed.

If the page remains unreliable, extraction fails; empty pages may be skipped, and a wholly empty document fails. An optional `OCR_ENABLED`
switch can add Tesseract OCR after those failures. OCR is **off by default**.
Missing system packages and languages produce a specific user-safe failure
rather than pretending OCR was performed.

## Evidence for the fallback

The [four-extractor comparison](extraction/comparison.md) measured three
unchanged public Arabic PDF fixtures before the fallback was added:

| Extractor | First-page reference anchors found | Inspector rejected |
| --- | ---: | ---: |
| pdfplumber | 0/3 | 3/3 |
| pypdfium2 | 3/3 | 0/3 |
| PyMuPDF | 2/3 | 0/3 |
| pypdf | 1/3 | 0/3 |

These are three **short known phrases**, not page-wide ground truth.
The new tests check that the PDFium fallback returns the phrases and preserves
the page number. This is evidence for recovering these regression cases, not
a general extraction-accuracy or retrieval-quality improvement. In particular,
a passing inspector cannot guarantee correct reading order in a long or mixed
PDF. Additional fixtures with independently transcribed ground truth are
needed to measure false positives and character/word error rates.

PyMuPDF is not used at runtime. It is available under AGPL-3.0 or a commercial
license and remains isolated to the optional comparison tooling.

## Inspector updates

`app/ingestion/arabic_words.txt` contains an explicitly maintained list
of common and technical Arabic terms. The reversed-token detector checks
normalized tokens against this list, requiring multiple reversed-token occurrences and a three-to-one advantage over normally oriented matches before
marking the page unreliable. Tests cover technical sentences, valid Arabic
and short mixed Arabic/English text. The list is **not** a language model,
and the thresholds are conservative, not calibrated. Text is never reversed
or joined automatically.

The existing presentation-form, disconnected-letter and unmapped-glyph checks
remain. Presentation forms alone are not a failure reason. Unicode NFKC is
applied selectively to normalized text while original text is retained.

## Configuration

```dotenv
PDFIUM_FALLBACK=true
OCR_ENABLED=false
```

`pypdfium2` is a normal, CPU-friendly runtime dependency. The project
does not install PyMuPDF by default.

To enable optional OCR locally, install the Python dependencies:

```powershell
py -3.11 -m pip install -e "./backend[ocr]"
```

Also install **Tesseract OCR** and its **Arabic and English** trained-data
packs on your machine, add the Tesseract executable to `PATH`, and confirm:

```powershell
tesseract --list-langs
```

The output must contain both `ara` and `eng`. On Ubuntu, install the
`tesseract-ocr`, `tesseract-ocr-ara`, and `tesseract-ocr-eng` system
packages. Python's `pytesseract` alone does not install this engine.

The OCR implementation rasterizes a page with PDFium at 180 DPI and passes it
to Tesseract with `lang="ara+eng"`. It does **not** require Poppler or
`pdf2image`. OCR is slower than text-layer extraction, may increase memory
pressure, and may misread numbers, diacritics, layouts and citations.
`OCR_ENABLED=true` will not work in the stock Dockerfile: it does not
install Tesseract, language packs or Python OCR extras. A custom image is
required before using OCR inside containers.

## Verification

```powershell
py -3.11 -m pip install -e "./backend[dev]"
py -3.11 -m pytest backend/tests/test_pdf_fallback.py -q
py -3.11 -m pytest backend/tests/test_arabic_pdf_quality.py -q
```

CI uses PDFium on the three fixtures and fake OCR tests. The real Tesseract
test skips if the executable, Python package or `ara+eng` language packs
are absent. CI does not install Tesseract or download models.

## Limitations

The fallback is triggered only when the inspector rejects or cannot extract
a page. Corrupted text that passes the inspector may still be indexed.
It also may fail on scanned PDFs unless OCR is enabled. Text positions,
multi-column order, mixed right-to-left segments, image-only content and
nonstandard fonts are not solved by the fallback. The initial three-fixture
measurement is a targeted regression check, not a broad quality benchmark.
