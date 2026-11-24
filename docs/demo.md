# Demonstration and final audit / العرض والتدقيق النهائي

## Demo (approximately 3 minutes)

Prepare the synthetic corpus with python -m eval.run --check, a working local provider, and two test accounts. Do not display secrets or private PDFs.

| Time | Action | Expected behavior, not a recorded result |
| --- | --- | --- |
| 0:00–0:30 | Explain bilingual PDF QA and show architecture | Clear distinction between structural citations and answer correctness |
| 0:30–1:00 | Upload ar_library.pdf and wait for ready | Document status visible |
| 1:00–1:35 | Ask كم تبلغ رسوم العضوية السنوية لمكتبة السحاب؟ | Reference is 85 ريالا on page 1; actual answer must be inspected |
| 1:35–2:00 | Open citation, inspect original page, switch UI language | Correct page; highlight only if unique match |
| 2:00–2:25 | Ask an unanswerable question, inspect result | Refusal is desired but not guaranteed; report unexpected answer honestly |
| 2:25–2:45 | Use second account to check isolation | First account's documents unavailable |
| 2:45–3:00 | Show measured retrieval results and limitations | Explain gate failure and reranking latency |

Record an actual screen capture only after a successful real-model run. Suggested clip: upload, ready status, generation progress, answer and page citation. Do not fabricate GIFs, screenshots, public URL or answer outcomes. No demo recording verified.

## Verified evidence

Reviewed revision d4f7ffb780ba92e2ba73d3ce44c41e59d6f2e722:
- [CI run 45500598240](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45500598240): 207 backend tests passed, 1 skipped, 2 warnings; lint, migration upgrade/downgrade, frontend build/tests and extraction comparison passed.
- [Production build 45500598241](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45500598241): local HTTPS health/readiness and UI smoke passed using certificate verification bypass on the runner only.
- [Measured retrieval results](eval/production-results.md) and [error analysis](error-analysis.md): historical synthetic-corpus retrieval, not answer accuracy.

## Release decision

GO for controlled local demonstration with synthetic data after real provider smoke succeeds. HOLD for stable public production. No external deployment, independent penetration/load test, consistent restore drill, held-out threshold calibration or real answer-level report is verified. Standard CI uses fake inference; real-model retrieval has a separate workflow. Recheck the exact final revision before release. Do not tag v1.0.0 on the strength of this document.

العربية: المشروع قابل للعرض محليًا بعد اختبار النموذج الفعلي، وليس معتمدًا للإنتاج. لا توجد شهادة أمان أو نشر خارجي موثق. النتائج المذكورة تاريخية ومحددة النطاق.
