# Engineering decisions and release gates / القرارات الهندسية

| Decision | Evidence or rationale | Remaining risk |
| --- | --- | --- |
| Dense default | Historical measured ranking and latency | Synthetic corpus only |
| Reranker opt-in | Better top rank, substantial CPU cost | Candidate sweep unmeasured |
| Cosine gate unchanged | Threshold 0.45 has not been calibrated | Zero historical negative refusal |
| Buffered QA | Reject malformed citation groups before display | No semantic entailment guarantee |
| PDFium fallback | Three upstream reference spans recovered | Full reading order unverified |
| Fail stale queued rows | Explicit retry avoids automatic poison-job loops | No durable queue or attempt fencing |
| Trust Caddy /32 only | Prevent arbitrary forwarded-header identities | Per-process limits, no distributed protection |
| Single-host Compose | Reproducible build and local HTTPS smoke | No external deployment or restore drill |

See [evaluation](eval/README.md), [measured results](eval/production-results.md), [error analysis](error-analysis.md), [security](security.md), and [deployment](deployment.md).

## Release gates

HOLD for a stable production release. CI and production build succeeded for the earlier Phase I commit dab6239a1a9db6cb3665961db7c518267ec4f45b ([CI](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45489281148), [build](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45489281182)). Recheck exact candidate; these are not external deployment results. Historical reranking measurements are available. Independent calibration, answer-level measurements, external TLS verification, backup/restore and abuse/load assessment remain outstanding. Do not publish a stable tag solely from passing CI.

العربية: نُبقي البحث الدلالي افتراضيًا والمراجع اختياريًا. لا تعني نجاح الاختبارات جاهزية الإنتاج أو صحة الإجابات. القرارات التجريبية تحتاج قياسات مستقلة.
