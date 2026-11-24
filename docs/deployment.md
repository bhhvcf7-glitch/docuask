# Production deployment / النشر

This is a single-host deployment candidate, not a certification of production readiness.

1. Provision a Linux host with Docker Compose v2, public DNS and ports 80/443. Point your hostname to the host.
2. Copy .env.example to .env. Set DOCUASK_DOMAIN, a unique POSTGRES_PASSWORD and random JWT_SECRET (at least 32 characters). Configure a working Ollama or OpenAI-compatible provider. Keep .env private.
3. Run `docker compose -f compose.production.yml up -d --build --wait`.
4. Verify `curl --fail https://YOUR_DOMAIN/health` and /ready without disabling certificate verification. Test registration, login, upload, QA, refresh and logout with a non-sensitive PDF. Back up PostgreSQL, uploads and Qdrant before upgrades; validate a consistent restore.

Caddy obtains TLS certificates for a valid public hostname; PostgreSQL, Qdrant and API have no host ports. The API runs migrations on startup; deploy one instance at a time. The workflow builds images and checks HTTPS on an ephemeral runner with a local test certificate. It does not deploy to an external host or publish images to a registry. A real deployment needs a host and operator-managed credentials. Do not treat the CI smoke check as an external deployment.

## العربية

جهّز خادم لينكس ودومينًا يشير إليه، وافتح المنافذ 80 و443. انسخ ملف البيئة وضع أسرارًا فريدة ومزوّد نموذج فعليًا، ثم شغّل أمر Docker Compose أعلاه. تحقّق من الشهادة دون تعطيل التحقق، واختبر رفع ملف غير حساس والإجابة وتحديث الجلسة. احتفظ بنسخ احتياطية لقاعدة البيانات والملفات. لا توجد عملية نشر خارجي تلقائية دون إعداد خادم ومفاتيح وصول.

## Security review

Refresh tokens are held in browser memory, rotated on a 401, with one in-flight refresh per tab. Reload requires login; HttpOnly cookies and cross-tab persistence are not implemented. Access JWTs survive logout until expiry. Caddy provides TLS and response security headers; the API has bounded per-process request limits. Production trusts only the dedicated Caddy peer; see Proxy trust below. Distributed limits are not implemented. Untrusted documents are separated from system instructions, not semantically verified. PDF parsing remains an untrusted-input risk; isolate the process for high-risk usage. No independent penetration test or load test has been completed. Use restricted data only after an appropriate security review.

The release audit additionally binds refresh retries to a session generation, and prevents a stale account token from borrowing the next signed-in account's token. Conversation answers are released only after their turn is committed. Recheck CI for the exact deployment candidate.

## Document recovery

At startup, stale queued and processing documents are marked failed. A periodic sweep checks queued documents only, using atomic conditional updates. STALE_QUEUED_MINUTES defaults to 30 and RECOVERY_INTERVAL_SECONDS to 60. Owners can retry failed documents. A slow active worker cannot be distinguished from a dead worker by elapsed time alone. Processing documents too recent at startup may remain stuck until another restart. Run one API instance; safe distributed recovery needs attempt fencing and leases or a durable queue. The SQL, file and vector operations do not share a transaction.

## Proxy trust

Production Caddy is the only trusted peer (172.30.50.2/32) on a dedicated proxy network. Caddy replaces incoming X-Forwarded-For with the direct client address. Do not expose the API port or attach untrusted workloads to that network. If the subnet conflicts with an existing network, change both the static address and trusted CIDR together. A CDN or another external proxy requires a separately reviewed trust configuration. The rate limiter is still per process; clients sharing a NAT address can share an auth bucket.

The proxy network assigns dynamic addresses from 172.30.50.128/25, outside Caddy's static address, to prevent the API from taking that address before Caddy starts.

## Operator runbook

Use a dedicated Linux VPS, Docker Engine and Compose v2, DNS A/AAAA records that resolve to the host, and firewall rules allowing HTTPS/HTTP and restricted administrator SSH only. Size CPU, RAM and disk by measuring the model and concurrent workload; no capacity benchmark is available. Do not expose Ollama, PostgreSQL, Qdrant or API ports publicly. Use a private provider endpoint and verify provider data-handling terms before sending document passages.

Clone and check out the exact reviewed commit. Set restrictive permissions before creating the environment file:

```bash
git clone https://github.com/bhhvcf7-glitch/docuask.git
cd docuask
git rev-parse HEAD
umask 077
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Generate separate secrets for the database and JWT. Edit .env, replacing all placeholders, setting DOCUASK_DOMAIN to the actual hostname and OLLAMA_URL to a reachable private endpoint (not container localhost). Keep OCR disabled in the stock image and reranking disabled until measured. Set APP_ENV=production. Do not paste secrets into issues or logs.

```bash
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml up -d --build --wait --wait-timeout 600
docker compose -f compose.production.yml ps
```

The API migrates the database on startup. Take a consistent backup before upgrades. From an independent client with public DNS and trusted CA validation:

```bash
curl --fail --show-error https://YOUR_DOMAIN/health
curl --fail --show-error https://YOUR_DOMAIN/ready
```

Both should return {"status":"ok"}. Never use -k for public acceptance. Verify HTTP redirect, TLS certificate hostname, registration, login, upload, ready status, real QA, citation page, refresh/logout, and second-account isolation. Use synthetic documents only. Record actual commit, date, hardware and results, not secrets. A health response does not verify LLM inference.

## Consistent cold backup and restore

Schedule downtime; stop all application writers and Qdrant before copying data. Run the following from the repository with the same Compose project name used for deployment (the examples assume the default docuask project). Adjust the volume names only after inspecting docker volume ls and confirm available disk. Never use docker compose down -v on production.

```bash
umask 077
mkdir -p backups
B="$(realpath backups)/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$B"
docker compose -f compose.production.yml stop web api qdrant
docker compose -f compose.production.yml exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$B/postgres.dump"
test -s "$B/postgres.dump"
for v in uploads_data qdrant_data; do
  docker volume inspect "docuask_$v" >/dev/null || exit 1
  docker run --rm -v "docuask_$v:/source:ro" -v "$B:/backup" alpine:3.22 tar -czf "/backup/$v.tar.gz" -C /source . || exit 1
done
(cd "$B" && sha256sum postgres.dump uploads_data.tar.gz qdrant_data.tar.gz > SHA256SUMS)
docker compose -f compose.production.yml up -d --wait --wait-timeout 600
```

Check each command for success; if a backup fails, do not declare it usable, and restart services after investigation. Encrypt backups and keep off-host copies with restricted access. Preserve the exact Git revision, image versions, configuration and secrets separately in secure storage. Caddy certificate state may also be backed up securely; model cache is reproducible subject to model revision availability. Database dumps and PDFs contain private data.

Restore into a new isolated project/host with matching PostgreSQL and Qdrant versions, fresh volumes and no public traffic. Verify SHA256SUMS, restore the SQL dump using pg_restore into an empty database, and unpack each archive into its corresponding empty volume while writers are stopped. Preserve file ownership. Start the reviewed application, verify migrations, compare row/point counts, test document viewing, ownership and actual QA, then record elapsed restore time. Do not overwrite the live volumes to test restoration. Roll back application and data together if a migration is incompatible; a code rollback alone may not be safe.

No backup or restore drill has been executed for a live deployment. These are operator instructions, not evidence of recovery.

## Demo acceptance

See [demo and final audit](demo.md) for the synthetic-data walkthrough. For a real host, keep public release on HOLD until independent TLS, backup restoration, security review and model evaluation are complete.
