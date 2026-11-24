# Retrieval evaluation

See [measured results](production-results.md). The corpus is synthetic; retrieval quality is not answer accuracy.

```bash
python -m eval.run --check
python -m pip install -e "./backend[dev,embeddings]"
python -m eval.run --output docs/eval/results.local.json
```

Download retrieval-comparison from [run 45419569734](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45419569734), extract compare.local.json into this directory, then run:

```bash
python -m eval.calibrate docs/eval/compare.local.json --mode dense --margin
python -m eval.calibrate docs/eval/compare.local.json --mode hybrid
```

Maximum returned cosine similarity reproduces the gate for the five returned hits. Top-ranked similarity and margin are diagnostics. The script needs no model or database. Select a candidate with an explicit recall constraint, then validate on held-out questions. The default remains 0.45 pending actual calibration. Gate recall does not establish that the reference page survives filtering.

## Answer-level evaluation (optional)

Use dedicated migrated PostgreSQL and Qdrant services with APP_ENV=test and an installed, running local Ollama model. The runner creates an isolated synthetic user and temporary vector collection, then cleans both. It uses real search_documents and answer_events, not the HTTP route, so rewriting, HTTP transport and conversation persistence are not measured. Never point it at production.

```bash
python -m eval.answers --run --limit 2 --output docs/eval/answers.smoke.local.json
python -m eval.answers --run --include-unanswerable --output docs/eval/answers.local.json
```

The default covers 72 answerable questions; the second command covers all 84. Remote inference requires explicit --allow-remote and may incur charges. No model calls are added to CI. The generated JSON is ignored by Git. Keep raw reports for independent review and record hardware and provider version separately. Errors are separate from refusals; undefined denominators yield null. Citation validity checks marker-to-source mappings against eligible hits; gold-page citation matches the labeled document and page. Neither metric proves entailment or answer correctness. The model is not explicitly warmed, so the first answer may include cold-start latency. No answer-level results are claimed until a real run is supplied.
