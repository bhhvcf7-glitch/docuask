# DocuAsk evaluation corpus

This is an openly published **synthetic** baseline, not an independent
real-world Arabic PDF benchmark. The four fictional, original source documents
and their labels are released under CC0-1.0. They contain two Arabic and two
English text-layer PDFs, two pages each. The document facts are unrelated to
real organizations; the 48 questions are intentionally withheld from PDF text.

The corpus has 40 answerable questions (10 per document, 5 per page) with
expected document, page and reference answer, plus eight unanswerable questions
(Arabic and English). All references are checked against actual extracted PDF
text before any model is loaded. The dataset was authored for regression
testing; it does not establish generalization to real user PDFs.

Files:
- `corpus/manifest.json`: original fictional document content, page by page
- `dataset/questions.jsonl`: 40 answerable and 8 unanswerable labels
- `build_corpus.py`: deterministic ReportLab PDF generator
- `run.py`: Qdrant dense evaluation using DocuAsk's existing extraction,
  chunking, embedding and vector-index implementations
- `metrics.py`: measured ranking, retrieval gate and latency statistics

PDFs are generated under `eval/corpus/pdfs/` (ignored by Git). GitHub Actions
builds and uploads them as a downloadable artifact. A local Arabic TrueType font
(DejaVu Sans on Linux, Arial/Tahoma on Windows) is required. The generated
PDFs are designed for Unicode extraction, not typographic Arabic shaping.
Real published Arabic PDF quality is handled separately in
`docs/arabic-extraction.md`.

## Commands

From the repository root with Python 3.11:

```powershell
py -3.11 -m pip install -e "./backend[dev,embeddings]"
py -3.11 -m eval.run --check
py -3.11 -m eval.run --output docs/eval/results.local.json
```

On Linux use `python -m ...` instead of `py -3.11 -m ...`. When an Arabic
font is not detected, pass `--font "C:/Windows/Fonts/arial.ttf"` or an
installed Arabic TrueType path.

The model defaults to `intfloat/multilingual-e5-small` on CPU and may
download weights on first use. The script uses in-memory Qdrant, so PostgreSQL,
the Qdrant service, the API, Ollama and paid LLMs are not required. It
evaluates the real dense embedding and vector-search path, not the
SQL/HTTP authorization layer (which already has independent integration tests).

For every question the script measures query embedding, Qdrant search and
total retrieval latency. It excludes PDF generation and initial indexing
from per-query latency but records total indexing time separately. Latency
p50/p95 use linear interpolation across the observed query timings. hit@1,
hit@3, hit@5 and MRR@5 match **both document and page**. MRR@5 assigns zero
to questions with no correct page in the top five.

`retrieval_gate_refusal_accuracy` reports the fraction of unanswerable
questions whose best similarity score is below the configured QA threshold.
`retrieval_gate_answerable_recall` reports the fraction of answerable
questions that pass the same gate. Neither is an LLM refusal rate or a
calibrated probability of factual support. No provider is called. The
script retains the real per-query similarity scores to support later
threshold analysis.

Results are saved as JSON in `docs/eval/results.local.json` by default.
The results file is ignored by Git until independently reviewed. Share
the measured JSON before choosing a new `QA_MIN_SCORE` or claiming that
chunking, hybrid retrieval or reranking improves relevance.

CI executes only `python -m eval.run --check` and lightweight deterministic
tests. It does not download embedding weights or publish benchmark scores.
