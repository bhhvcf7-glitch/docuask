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
