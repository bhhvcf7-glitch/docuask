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

These figures were recorded in the previous evaluation report. Reranking metrics are not yet available at the time of this change. No end-to-end answer accuracy is measured. Dense remains default; the synthetic dataset and zero refusal accuracy are important limitations.

العربية: تفوق البحث الدلالي في ترتيب أول نتيجة وفي زمن الاستجابة في هذه العينة الاصطناعية، ولا تكفي النتائج لإثبات جودة عامة أو صحة الإجابات. لم تنجح بوابة التشابه في رفض الأسئلة غير القابلة للإجابة في هذه التجربة.
