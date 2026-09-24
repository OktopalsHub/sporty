# Phase 24 production readiness

Phase 24 is the final production-readiness pass before a controlled release.

## Configuration gates

Production startup now fails fast when:

- `APP_ENV=production` and `API_KEY` is missing.
- `APP_ENV=production` and `TRUSTED_HOSTS` is empty.

Production secrets must come from the deployment platform. Do not copy the local Compose API key into production.

## Deployment checklist

Before production:

- [ ] Configure Neon pooled `DATABASE_URL`.
- [ ] Run `alembic upgrade head` once through the deployment pipeline.
- [ ] Configure managed Redis `REDIS_URL` using TLS where supported.
- [ ] Configure a strong production `API_KEY`.
- [ ] Set `TRUSTED_HOSTS` to the real API hostname.
- [ ] Set `FRONTEND_ORIGINS` to the real frontend origin(s).
- [ ] Set `DOCS_ENABLED=false` unless API documentation is intentionally public.
- [ ] Configure Logfire.
- [ ] Deploy the API separately from the background worker.
- [ ] Confirm `/api/v1/health` and `/api/v1/ready`.
- [ ] Confirm protected API routes reject requests without `X-API-Key`.
- [ ] Confirm Redis failure causes protected requests to fail closed when configured.
- [ ] Confirm worker jobs complete, retry, and eventually fail correctly.
- [ ] Run the Phase 23 load test against staging before production traffic.
- [ ] Review p95/p99 latency, error rate, DB connections, Redis connections, and queue depth.
- [ ] Verify rollback procedure and database migration compatibility.

## Local production-like validation

The Docker Compose stack uses `APP_ENV=production` with a non-production local API key so the security startup gate is exercised locally.

Start it with:

```bash
docker compose up --build -d
```

Check:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/ready
curl -H "X-API-Key: local-development-only" http://127.0.0.1:8000/api/v1/meta
```

Do not reuse `local-development-only` outside the local Compose environment.
