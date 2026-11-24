# Production deployment / النشر

This is a single-host deployment candidate, not a certification of production readiness.

1. Provision a Linux host with Docker Compose v2, public DNS and ports 80/443. Point your hostname to the host.
2. Copy .env.example to .env. Set DOCUASK_DOMAIN, a unique POSTGRES_PASSWORD and random JWT_SECRET (at least 32 characters). Configure a working Ollama or OpenAI-compatible provider. Keep .env private.
3. Run `docker compose -f compose.production.yml up -d --build --wait`.
4. Verify `curl --fail https://YOUR_DOMAIN/health` and /ready without disabling certificate verification. Test registration, login, upload, QA, refresh and logout with a non-sensitive PDF. Back up PostgreSQL and uploads before upgrades.

Caddy obtains TLS certificates for a valid public hostname; PostgreSQL, Qdrant and API have no host ports. The API runs migrations on startup; deploy one instance at a time. The workflow builds images and checks HTTPS on an ephemeral runner with a local test certificate. It does not deploy to an external host or publish images to a registry. A real deployment needs a host and operator-managed credentials. Do not treat the CI smoke check as an external deployment.

## العربية

جهّز خادم لينكس ودومينًا يشير إليه، وافتح المنافذ 80 و443. انسخ ملف البيئة وضع أسرارًا فريدة ومزوّد نموذج فعليًا، ثم شغّل أمر Docker Compose أعلاه. تحقّق من الشهادة دون تعطيل التحقق، واختبر رفع ملف غير حساس والإجابة وتحديث الجلسة. احتفظ بنسخ احتياطية لقاعدة البيانات والملفات. لا توجد عملية نشر خارجي تلقائية دون إعداد خادم ومفاتيح وصول.

## Security review

Refresh tokens are held in browser memory, rotated on a 401, with one in-flight refresh per tab. Reload requires login; HttpOnly cookies and cross-tab persistence are not implemented. Access JWTs survive logout until expiry. Caddy provides TLS and response security headers; the API has bounded per-process request limits. Anonymous clients share the proxy peer bucket because forwarded headers are disabled. This limits abuse but needs trusted proxy configuration and distributed limits for scale. Untrusted documents are separated from system instructions, not semantically verified. PDF parsing remains an untrusted-input risk; isolate the process for high-risk usage. No independent penetration test or load test has been completed. Use restricted data only after an appropriate security review.

The release audit additionally binds refresh retries to a session generation, and prevents a stale account token from borrowing the next signed-in account's token. Conversation answers are released only after their turn is committed. These changes require fresh CI verification.

## Document recovery

At startup, stale queued and processing documents are marked failed. A periodic sweep checks queued documents only, using atomic conditional updates. STALE_QUEUED_MINUTES defaults to 30 and RECOVERY_INTERVAL_SECONDS to 60. Owners can retry failed documents. A slow active worker cannot be distinguished from a dead worker by elapsed time alone. Processing documents too recent at startup may remain stuck until another restart. Run one API instance; safe distributed recovery needs attempt fencing and leases or a durable queue. The SQL, file and vector operations do not share a transaction.

## Proxy trust

Production Caddy is the only trusted peer (172.30.50.2/32) on a dedicated proxy network. Caddy replaces incoming X-Forwarded-For with the direct client address. Do not expose the API port or attach untrusted workloads to that network. If the subnet conflicts with an existing network, change both the static address and trusted CIDR together. A CDN or another external proxy requires a separately reviewed trust configuration. The rate limiter is still per process; clients sharing a NAT address can share an auth bucket.

The proxy network assigns dynamic addresses from 172.30.50.128/25, outside Caddy's static address, to prevent the API from taking that address before Caddy starts.
