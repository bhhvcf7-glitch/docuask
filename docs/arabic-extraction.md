# Arabic PDF extraction: measured limitations

DocuAsk extracts text from PDFs with `pdfplumber`, preserving the original
extraction for citations. This page records observed behavior on publicly
available upstream PDF fixtures, not a representative Arabic accuracy benchmark.

## Sources and measured output

All three PDFs are checked into `backend/tests/fixtures/arabic/` without
modification. The source repositories are publicly licensed (jsPDF and Tabula:
MIT; PDF.js: Apache-2.0). The files retain their upstream provenance.

| Local fixture | Upstream file | Pages | Extracted chars | Arabic-block chars | Arabic presentation-form chars |
| --- | --- | ---: | ---: | ---: | ---: |
| `jspdf_arabic.pdf` | [jsPDF reference](https://github.com/parallax/jsPDF/blob/master/test/reference/arabic.pdf) | 1 | 24 | 0 | 19 |
| `pdfjs_arabic_cid.pdf` | [PDF.js Arabic CID](https://github.com/mozilla/pdf.js/blob/master/test/pdfs/ArabicCIDTrueType.pdf) | 1 | 79 | 24 | 44 |
| `tabula_arabic.pdf` | [Tabula Arabic](https://github.com/tabulapdf/tabula-java/blob/master/src/test/resources/technology/tabula/arabic.pdf) | 1 | 138 | 3 | 80 |

Measurements are from GitHub Actions on 2026-11-24, using `page.extract_text(layout=False)`.
Presentation forms (U+FB50–U+FDFF and U+FE70–U+FEFC) lie outside the
conventional U+0600–U+06FF Arabic block, which explains the low Arabic-block
counts. The counts describe Unicode ranges, **not** character error rates.

Observed examples (raw `pdfplumber` output):

- jsPDF: `ﺖﺌﺷ ﺎﻣ ﻊﻨﺻﺎﻓ ﺢﺘﺴﺗ ﻢﻟ ﺍﺫﺇ`
- PDF.js: `ﺔﻴﺑﺮﻌﻟا طﻮﻄﳋا عاﻮﻧا`
- Tabula: `ﺎﺒﺣﺮﻣ ﻥﺎﻄﻠﺳ ﻲﻤﺳﺍ`, with mixed Latin text and numbers

These samples demonstrate extraction problems including Arabic presentation
forms and visually ordered words. All three trigger the conservative reversed-
word detector and are rejected rather than embedded as potentially misleading
source text. This is not proof that every page of every Arabic PDF is broken.

## Extractor comparison

The separate [four-extractor comparison](extraction/comparison.md) measures
raw output from pdfplumber, pypdfium2, PyMuPDF and pypdf on the same three
fixtures. It retains text samples and inspector decisions; it does not
interpret a passing heuristic as proof of correct Arabic reading order.
The production extraction chain has not changed. The comparison tool is
optional, and PyMuPDF must not be added to the default runtime without a
separate license decision.

## Detection and behavior

`app.ingestion.quality.inspect_arabic` returns issue codes:

- `presentation_forms`: presentation-form glyphs occur; this signal alone is
  **not** a reason to reject a page.
- `suspected_reversed_words`: at least three tokens match reversed common
  Arabic words, and substantially outnumber the matching forward-order words.
- `disconnected_letters`: at least 10 Arabic tokens, with at least eight
  isolated one-letter tokens and 75% or more isolated tokens.
- `unmapped_glyphs`: repeated `(cid:123)` placeholders or a high
  proportion of Unicode replacement characters.

Severe indicators cause `ExtractionError`, so the existing ingestion service
marks the document failed instead of indexing unreliable content. Less severe
presentation-form findings are logged and retained. No text is blindly
reversed; the detector does not attempt to reconstruct reading order.

`normalize_arabic` decomposes **only Arabic presentation forms** using
Unicode NFKC, for example `ﻻ` to `لا` or `ﷲ` to `الله`.
The original PDF extraction is retained separately. This decomposition
does not repair visual-order words, incorrect multi-column reading order,
lost spaces, or incorrect Unicode mappings.

## Limits

The reversed-word test uses a small common-word list; it can miss reversed
technical vocabulary or flag unusually written but valid passages.
A fragmented-text threshold can miss short damaged lines. An unmapped-CID
pattern may not identify custom fonts with misleading ToUnicode mappings.
Some visually reversed text lacks presentation forms entirely. Arabic
ligatures may already have been lost during font decoding, in which case
NFKC cannot restore them. PDF text may also contain a mixture of logical-
and visual-order runs, making global reversal unsafe.

Scanned PDFs still need OCR. DocuAsk does not claim to repair all Arabic PDFs,
and this small regression set is not a ground-truth CER/WER evaluation.
A larger, independently transcribed corpus is needed before tuning
heuristics or comparing extractors.

## Reproduce

From the repository root:

```bash
python -m pip install -e './backend[dev]'
python scripts/inspect_arabic_fixtures.py
python -m pytest backend/tests/test_arabic_pdf_quality.py -q
python -m pytest backend/tests/test_pdf_extraction.py -q
```

CI runs the fixture inspector and the tests without downloading OCR/model
weights or accessing third-party APIs.
