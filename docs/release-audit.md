# v1.0.0 release audit

Historical audit; current gates are in [decisions.md](decisions.md). Status remains HOLD. Historical reranking measurements are now available; they do not establish production readiness.

Reviewed browser session renewal, API calls, conversation persistence, refresh token family rotation, request limiting, deployment configuration and evaluation reporting. Fixed cross-account token substitution and stale asynchronous UI results, delayed conversation output until persistence succeeds, excluded local dependency/build/upload directories from Docker context, and documented DOCUASK_DOMAIN.

Remaining release risks: no independent penetration or load test; no distributed rate limiter; refresh tokens held in browser memory; access JWTs survive logout until expiry; PDF extraction/highlighting limitations; no semantic entailment verification; retrieval refusal accuracy zero on the synthetic baseline; no externally verified deployment or backup restore drill. Do not claim production readiness. Reranking metrics were pending at the original audit; see [measured results](eval/production-results.md). Recheck exact HEAD workflows before tagging.
