# Retrieval error analysis / تحليل أخطاء الاسترجاع

## Evidence and scope

Raw compare.local.json from [run 45485366656, artifact 14964705675](https://github.com/bhhvcf7-glitch/docuask/actions/runs/45485366656/artifacts/14964705675), evaluated commit c92026c47c9437f8c7ccd545ac240b9667b12865. Dataset SHA-256: f7e30ad206bd990fe4e8cffdecbf75ddc3d0bac4c99d4e997dc75b2ebe3c270c. Six synthetic PDFs, 36 pages, 73 chunks, 72 answerable and 12 unanswerable questions. Threshold 0.45. Dense hit@1 0.7639, hit@3 0.8889, hit@5 0.9861, MRR@5 0.8387; p50 26.978 ms, p95 33.443 ms. Rank uses both filename and page, taking the first matching hit.

Rank counts: 55 first, 5 second, 4 third, 3 fourth, 4 fifth, 1 absent. The five worst cases (missing first, then descending rank, ties by ID) are:

| ID | Reference answer | Expected PDF/page | First hit PDF/page | Gold rank | First score | First gold score |
| --- | --- | --- | --- | --- | --- | --- |
| ar_water_06 | الثلاثاء | ar_water.pdf/3 | ar_water.pdf/1 | absent | 0.8501574 | unavailable |
| ar_library_06 | شهر مايو | ar_library.pdf/3 | ar_library.pdf/1 | 5 | 0.8455556 | 0.8377065 |
| ar_library_east_10 | الطابق الثاني | ar_library_east.pdf/5 | ar_library_east.pdf/6 | 5 | 0.81729746 | 0.8125955 |
| ar_water_10 | ثلاث ساعات | ar_water.pdf/5 | ar_water.pdf/1 | 5 | 0.85093534 | 0.84553707 |
| ar_water_12 | 177 | ar_water.pdf/6 | ar_water.pdf/1 | 5 | 0.8561592 | 0.85091025 |

## Evidence and hypotheses

The manifest contains the labeled answer sentences. Repeated administrative boilerplate occurs across pages, while the target facts occupy individual sentences. This supports a hypothesis of weak discrimination between pages, not a proven causal attribution.

- ar_water_06: the first page contains reservoir capacity, whereas page 3 contains the weekly inspection day. All five hits are from the correct document but none from page 3. Investigate deeper candidate recall and lexical matching.
- ar_library_06: page 3 contains the delivery start month. Page 1 contains membership fees and heritage cataloging. The small score difference suggests testing sentence-focused chunks.
- ar_library_east_10: page 5 of the other library appears fourth and contains a different floor (third instead of second). The correct document/page appears fifth. This is direct evidence of cross-document confusion; test entity-aware retrieval, not a global page-number match.
- ar_water_10 and ar_water_12: page 5 contains closure duration and page 6 contains the fault-report number. Both rank fifth behind page 1. Test shorter chunks and lexical retrieval without changing multiple variables at once.

The raw artifact records page locations and scores, not chunk identifiers or text. It cannot establish that an individual retrieved chunk contains the answer, or diagnose an extraction or chunk-boundary defect. Corpus validation checks reference text at page level. The five cases are Arabic, but this selected tail is not proof of a general language disadvantage.

All twelve unanswerable questions pass the 0.45 gate; maximum returned cosine scores range from 0.8089341 to 0.85236216. This is retrieval-gate behavior, not observed LLM hallucinations.

## Follow-up experiment

1. Export candidate chunk IDs, original text and pre/post gate ranks for the synthetic corpus only.
2. Compare fixed-depth candidate recall, sentence-focused chunking, and lexical fusion separately against dense. Keep questions and model fixed. Use held-out documents for final selection.
3. Calibrate the gate on a separate development split; report recall and refusal together.
4. Measure answer-level behavior separately. Do not tune the default from five selected failures.

No runtime retrieval settings are changed by this analysis.

العربية: أظهر التقرير الخام غياب الصفحة المرجعية عن أول خمس نتائج لسؤال واحد وتأخرها إلى المركز الخامس لأربعة أسئلة أخرى. يتكرر النص العام بين الصفحات، لكن إثبات أثره يحتاج تجربة مضبوطة. لا تثبت هذه النتائج خطأ الاستخراج أو صحة الإجابات، ولا تبرر تعديل الإعدادات الافتراضية دون قياس مستقل.
