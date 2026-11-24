# v1.0.0 release audit

Status: HOLD. No stable tag or external deployment is authorized by this audit until the exact candidate passes CI and production HTTPS smoke tests and real reranking measurements are available.

Reviewed browser session renewal, API calls, conversation persistence, refresh token family rotation, request limiting, deployment configuration and evaluation reporting. Fixed cross-account token substitution and stale asynchronous UI results, delayed conversation output until persistence succeeds, excluded local dependency/build/upload directories from Docker context, and documented DOCUASK_DOMAIN.

Remaining release risks: no independent penetration or load test; no distributed rate limiter; refresh tokens held in browser memory; access JWTs survive logout until expiry; PDF extraction/highlighting limitations; no semantic entailment verification; retrieval refusal accuracy zero on the synthetic baseline; no externally verified deployment or backup restore drill. Do not claim production readiness. Real reranking metrics remain pending at time of commit. Recheck exact HEAD workflows before tagging.
