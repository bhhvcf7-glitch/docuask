# Measured retrieval baseline / نتائج التقييم

Source: GitHub Actions run [45419569734](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45419569734), artifact 14933163421. Six synthetic bilingual PDFs, 36 pages, 84 questions (72 answerable, 12 unanswerable).

| Metric | Dense | Hybrid |
| --- | ---: | ---: |
| Hit@1 | 0.7639 | 0.7361 |
| Hit@3 | 0.8889 | 0.8889 |
| Hit@5 | 0.9861 | 0.9861 |
| MRR@5 | 0.8387 | 0.8255 |
| p50 total ms | 27.23 | 55.65 |
| p95 total ms | 33.67 | 63.09 |
| Retrieval-gate refusal accuracy | 0 | 0 |

These figures were recorded in the previous evaluation report. No end-to-end answer accuracy is measured. Dense remains default; the synthetic dataset and zero refusal accuracy are important limitations.

العربية: تفوق البحث الدلالي في ترتيب أول نتيجة وفي زمن الاستجابة في هذه العينة الاصطناعية، ولا تكفي النتائج لإثبات جودة عامة أو صحة الإجابات. لم تنجح بوابة التشابه في رفض الأسئلة غير القابلة للإجابة في هذه التجربة.

## Comparison with reranking

Same workflow, job 138535050384, artifact 14934842876, evaluated commit e1fc7948c86ac59133fe571a1841e9bc05b49405. Values verified in the execution logs. Compare modes within this experiment.

| Metric | Dense | Hybrid | Hybrid + reranker |
| --- | ---: | ---: | ---: |
| Hit@1 | 0.7639 | 0.7361 | 0.9167 |
| Hit@3 | 0.8889 | 0.8750 | 1.0000 |
| Hit@5 | 0.9861 | 0.9722 | 1.0000 |
| MRR@5 | 0.8387 | 0.8208 | 0.9583 |
| Gate recall | 1.0000 | 1.0000 | 1.0000 |
| Gate refusal accuracy | 0 | 0 | 0 |
| Retrieval p50 (ms) | 27.790 | 55.425 | 15766.760 |
| Retrieval p95 (ms) | 32.980 | 62.613 | 18054.897 |

No answer accuracy is measured. Reranking remains optional.
