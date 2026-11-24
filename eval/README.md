# DocuAsk evaluation corpus

The benchmark uses six original fictional text-layer PDFs, released under
CC0-1.0. Three are Arabic and three are English. Each document has six pages,
giving 36 pages in total. The question file contains 72 answerable questions
(two per page, labeled with document and page) and 12 unanswerable questions.

The paired libraries and paired transit reports intentionally repeat the same
topics with different facts. Each page contains more than 1,100 characters of
operational context. Labeled answers appear in the middle and later portions
of these long pages, not only in page titles. The validator requires at least
two chunks per page under the current DocuAsk chunker.

This is a controlled **synthetic regression corpus**, not a representative
sample of independently published PDFs. Some background text is intentionally
repetitive. It tests retrieval ranking among distractors but cannot establish
real-world relevance or Arabic rendering quality.

## Files

- `corpus/manifest.json`: original fictional reference text for every page
- `dataset/questions.jsonl`: questions, reference answers and document/page labels
- `build_corpus.py`: deterministic PDF generation with a local TrueType font
- `run.py`: validation and CPU dense retrieval through the existing components
- `metrics.py`: hit@1/3/5, MRR@5, retrieval-gate accuracy and p50/p95 latency

The generated PDFs are saved under `eval/corpus/pdfs/`, ignored by Git and
uploaded as a GitHub Actions artifact. The benchmark uses real `pdfplumber`
extraction, `chunk_pages`, `multilingual-e5-small` and in-memory Qdrant.
It reports the actual number of indexed chunks, including per-document counts.

## Commands

From the repository root on Windows:

```powershell
py -3.11 -m pip install -e "./backend[dev,embeddings]"
py -3.11 -m eval.run --check
py -3.11 -m eval.run --output docs/eval/results.local.json
```

For a lightweight validation, install only `./backend[dev]` and run
`--check`; this does not download model weights. On Linux use
`python -m` instead of `py -3.11 -m`. If Arabic fonts cannot be found,
add `--font "C:/Windows/Fonts/arial.ttf"` or an installed Arabic TTF path.

The full evaluation downloads `intfloat/multilingual-e5-small` if necessary
and runs on CPU. It does not require PostgreSQL, a Qdrant server, Ollama or paid
API credentials. The script reports indexed chunk count, hit@1, hit@3, hit@5,
MRR@5 and latency p50/p95 for query embedding, vector search and end-to-end
retrieval. Ranking counts a hit only when **both document and page** match.
MRR@5 is zero if no matching page appears in the first five results.

The refusal numbers measure only whether the top similarity score passes the
existing `QA_MIN_SCORE` threshold. They do not test LLM refusal or factual
correctness. A non-answerable question might still match a thematically similar
passage. Indexing time is reported separately from query latency.

`docs/eval/results.local.json` is ignored by Git. Share that measured JSON
before setting a new score threshold or claiming that retrieval improved.
The CI run validates PDF text and answer labels, exercises the evaluation
code using fake embeddings and in-memory Qdrant, and runs no real model.

Three independent, difficult Arabic PDF extraction fixtures remain documented
in `docs/arabic-extraction.md`; they are intentionally not part of this
synthetic retrieval benchmark.
