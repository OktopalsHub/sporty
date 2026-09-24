# Sporty

AI-powered football prediction and SportyBet ticket builder.

## Development

FastAPI backend with isolated provider adapters, prediction strategies, ticket generation, and persistent selection history.

Install development dependencies:

```bash
pip install -e ".[dev]"
```

Run the API locally:

```bash
uvicorn app.main:app --reload
```

Run quality checks:

```bash
ruff check .
pytest
pytest --cov=app --cov-report=term-missing
```

## Database

The application uses SQLAlchemy with PostgreSQL as the primary database.

For local development:

```env
DATABASE_URL=postgresql+psycopg://sporty:sporty@localhost:5432/sporty
```

The application does not create tables automatically at startup. Use Alembic to apply the schema before starting the API:

```bash
alembic upgrade head
```

## Redis

Redis is used for distributed API rate limiting and the background prediction queue.

For local development:

```env
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
```

Rate limits are enforced per API key when `X-API-Key` is configured, otherwise per client IP. The health and readiness endpoints are excluded. If Redis is temporarily unavailable, requests are allowed through so a cache/rate-limit dependency does not become a total API outage.

The readiness endpoint checks both PostgreSQL and Redis.

## API health

- `GET /api/v1/health` is the liveness check. It does not require PostgreSQL or Redis.
- `GET /api/v1/ready` is the readiness check. It verifies PostgreSQL and Redis connectivity.
- Every API response includes an `X-Request-ID` header.
- Rate-limited responses return `429`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After`.

## Docker

Build and run the production-like PostgreSQL and Redis stack:

```bash
docker compose up --build
```

The container entrypoint runs `alembic upgrade head` before starting the API. Production deployments should use the same migration-first pattern and provide secrets through the deployment environment, not the image.

## Phase 13 frontend integration contract

The backend exposes a stable frontend-facing contract through FastAPI OpenAPI and a metadata endpoint.

### Bootstrap

- `GET /api/v1/meta` returns the supported markets and ticket strategies.
- `GET /api/v1/health` is the liveness check.
- `GET /api/v1/ready` is the database and Redis readiness check.
- The API returns `X-Request-ID` on every response.

### Selection flow

1. Create a session with `POST /api/v1/selections/sessions`.
2. Add the exact prediction object with `POST /api/v1/selections/sessions/{session_id}`.
3. Restore the session with `GET /api/v1/selections/sessions/{session_id}`.
4. Remove one prediction with `DELETE /api/v1/selections/sessions/{session_id}/{prediction_id}`.
5. Delete the complete session with `DELETE /api/v1/selections/sessions/{session_id}`.

The frontend must keep the prediction `id`, `event_id`, `market_id`, `specifier`, and `outcome_id` returned by the generator. The backend validates the prediction ID and never substitutes another prediction.

### Ticket flow

- `POST /api/v1/tickets/{session_id}/build` validates the stored selections against the current provider feed and creates the share ticket.
- The backend refreshes provider odds before calculating the final combined odds.
- The frontend should display the returned `selections` and `combined_odds`, not recalculate provider odds locally.
- Failed provider validation does not create successful ticket history.

### Strategy endpoints

- `POST /api/v1/generators/1k/generate`
- `POST /api/v1/generators/5k/generate`
- `POST /api/v1/generators/weekly-safe/generate`
- Market generators are available under `/api/v1/generators/*/generate`.

### CORS

Set `FRONTEND_ORIGINS` to a comma-separated list of allowed frontend origins.

FastAPI OpenAPI is available at `/docs` and `/openapi.json` for frontend client generation.

## CI

GitHub Actions runs on pushes and pull requests. It installs the development dependencies, starts PostgreSQL and Redis, runs Ruff, runs the test suite, and applies the Alembic migrations against PostgreSQL.

The CI workflow is the minimum merge gate.

## Phase 15 production hardening

PostgreSQL is the primary database for development, CI, and deployment.

Database connections use SQLAlchemy pooling with configurable:

- `DATABASE_POOL_SIZE`
- `DATABASE_MAX_OVERFLOW`
- `DATABASE_POOL_TIMEOUT`

Set `API_KEY` in a protected deployment environment to require `X-API-Key` on API routes. The liveness and readiness endpoints remain public so container and platform health checks can run without credentials.

Example:

```env
API_KEY=replace-with-a-secret
```

Do not commit real API keys to the repository.

## Phase 16 production reliability

Phase 16 adds Redis-backed distributed rate limiting so multiple API instances share the same request budget. It also makes Redis part of readiness checks and local/CI infrastructure.

## Background prediction jobs

Long-running prediction generation can be submitted to the Redis-backed worker queue.

Create a job:

```http
POST /api/v1/jobs
Content-Type: application/json

{
  "job_type": "1k",
  "hours": 168
}
```

Supported job types are `1k`, `5k`, `weekly_safe`, `over_1_5`, `over_2_5`, `btts`, `under_2_5`, and `under_4_5`.

The API returns `202 Accepted` with a job ID. Poll `GET /api/v1/jobs/{job_id}` for status, progress, retries, errors, and the completed result.

The Docker stack now runs API, worker, PostgreSQL, and Redis as separate services. The worker consumes the `jobs:prediction` Redis queue and retries failed jobs up to three attempts.

## Phase 18 observability

The application uses Pydantic Logfire for production observability instead of exposing a Prometheus endpoint.

Logfire instruments:

- FastAPI request traces and validation errors
- SQLAlchemy database queries
- HTTPX outbound requests, including SportyBet calls
- Redis commands
- Prediction worker spans
- Prediction job completion, failure, retry, and duration metrics
- Standard application logs can be added to the same Logfire project when needed

FastAPI Cloud can connect a Logfire project to an app and inject the `LOGFIRE_TOKEN` environment variable as an encrypted secret. The application uses `send_to_logfire="if-token-present"`, so local tests do not require a Logfire token.

For local development:

```env
LOGFIRE_TOKEN=
LOGFIRE_SEND_TO_LOGFIRE=if-token-present
LOGFIRE_SERVICE_NAME=Sporty
LOGFIRE_SERVICE_VERSION=0.1.0
LOGFIRE_ENVIRONMENT=development
```

For FastAPI Cloud, connect the Logfire integration to the deployed app and let FastAPI Cloud provide `LOGFIRE_TOKEN`.

The old `GET /api/v1/metrics` Prometheus endpoint has been removed. No Prometheus server is required.

## FastAPI Cloud

Production deployment should use FastAPI Cloud with the following external services:

- Neon PostgreSQL
- Managed Redis
- Logfire

The application remains responsible for API routes, background jobs, migrations, and business logic.

## Phase 19 production database

The production database is PostgreSQL hosted by Neon. The application still uses SQLAlchemy, psycopg, and Alembic, so no Neon-specific ORM layer is required.

Set `DATABASE_URL` to the Neon connection string. Prefer Neon's pooled connection string for the API and worker when the deployment can create multiple application instances. Keep the `sslmode=require` parameter from the Neon connection string.

Production database settings are configurable through:

- `DATABASE_POOL_SIZE`
- `DATABASE_MAX_OVERFLOW`
- `DATABASE_POOL_TIMEOUT`
- `DATABASE_POOL_RECYCLE`
- `DATABASE_CONNECT_TIMEOUT`

The defaults are intentionally conservative for autoscaling deployments. Each API or worker instance has its own connection pool, so increasing pool sizes also increases the possible number of PostgreSQL connections.

Example:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=300
DATABASE_CONNECT_TIMEOUT=10
```

Apply schema changes with Alembic:

```bash
alembic upgrade head
```

Do not put the Neon password or connection string in the repository. Store `DATABASE_URL` as a FastAPI Cloud secret.

Local Docker development continues to use the local PostgreSQL service. Neon is the production database provider, not a required local dependency.


## Phase 20 managed Redis

Production Redis is designed to use a managed Redis-compatible service. The application keeps the standard `redis-py` client and reads one `REDIS_URL`, so the provider can be changed without changing application code.

For production, use the TLS connection URL supplied by the managed Redis provider:

```env
REDIS_URL=rediss://USERNAME:PASSWORD@HOST:PORT/0
REDIS_TIMEOUT=5
REDIS_MAX_CONNECTIONS=20
REDIS_HEALTH_CHECK_INTERVAL=30
```

The `rediss://` scheme enables TLS in `redis-py`. Upstash Redis provides TLS TCP connection strings and is compatible with the Redis protocol, so it can be used without an application-specific adapter.

Redis is shared by all API instances and the background worker for:

- distributed rate limiting
- the prediction job queue
- job locks
- short-lived application state

Keep local Docker Redis for development. Do not commit managed Redis credentials.

The Redis client uses connection pooling, TCP keepalive, and periodic health checks. The timeout is long enough for the worker's blocking queue read while still bounding connection and command failures.

## Phase 21 FastAPI Cloud deployment

Production API deployment targets FastAPI Cloud. FastAPI Cloud supports standard Python projects and can deploy this project with `fastapi deploy`. The project now declares the FastAPI CLI dependency and an explicit `app.main:app` entrypoint.

Production flow:

```text
GitHub main
   |
   v
GitHub Actions
   |
   +--> Alembic migrations -> Neon PostgreSQL
   |
   +--> fastapi deploy -> FastAPI Cloud
   |
   +--> API instances -> managed Redis
   |
   +--> Logfire
```

FastAPI Cloud can autoscale API instances, so the API must remain stateless. Database state lives in Neon and shared Redis state lives in the managed Redis service.

### Required FastAPI Cloud secrets

Configure these repository secrets before enabling production deployment:

- `FASTAPI_CLOUD_TOKEN`
- `FASTAPI_CLOUD_APP_ID`
- `DATABASE_URL`

The deploy workflow applies Alembic migrations to the Neon database before deploying the new API version. FastAPI Cloud's CI deployment flow uses a deploy token and app ID from GitHub secrets.

### Required FastAPI Cloud environment variables

Configure the runtime environment in FastAPI Cloud:

```env
APP_ENV=production
DATABASE_URL=<Neon pooled connection string>
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=300
DATABASE_CONNECT_TIMEOUT=10

REDIS_URL=<managed Redis rediss:// URL>
REDIS_TIMEOUT=5
REDIS_MAX_CONNECTIONS=20
REDIS_HEALTH_CHECK_INTERVAL=30

API_KEY=<production API key>
FRONTEND_ORIGINS=<allowed frontend origins>

LOGFIRE_TOKEN=<Logfire token>
LOGFIRE_SEND_TO_LOGFIRE=if-token-present
LOGFIRE_SERVICE_NAME=Sporty
LOGFIRE_SERVICE_VERSION=0.1.0
LOGFIRE_ENVIRONMENT=production
```

Do not put production secrets in `.env.example`, Docker Compose, or the repository.

### Background worker

FastAPI Cloud deployment is for the HTTP API. The existing `app.job_worker` is a separate long-running process and should not be started inside every autoscaled API replica.

The worker must run on a separate long-running worker service/container with the same:

- `DATABASE_URL`
- `REDIS_URL`
- SportyBet configuration
- Gemini configuration when required

The local Docker Compose worker remains the reference implementation for this process. The managed Redis queue allows the API and worker to share jobs across hosts.

This separation avoids creating one worker per autoscaled API replica and keeps the queue consumer independent from request-driven API scaling.

### Deployment commands

Local FastAPI Cloud deployment:

```bash
fastapi login
fastapi deploy
```

CI deployment runs automatically on pushes to `main`. FastAPI Cloud also supports a generated CI setup through `fastapi cloud setup-ci`.

### Production migration rule

Do not run `alembic upgrade head` from the API application startup. FastAPI Cloud uses rolling deployments and multiple replicas, so migrations are applied once by the deployment workflow before the new API version is deployed.



## Phase 22 production security

Production deployments use defense-in-depth controls:

- `X-API-Key` is mandatory for API routes when `APP_ENV=production`.
- Health and readiness endpoints remain public for platform health checks.
- API keys are compared with constant-time comparison.
- Redis rate limiting fails closed in production when request protection is unavailable.
- Trusted Host validation rejects unexpected Host headers.
- Security response headers are enabled by default.
- FastAPI Swagger, ReDoc, and OpenAPI endpoints can be disabled with `DOCS_ENABLED=false`.
- Production secrets must be supplied by the deployment platform and never committed to Git.
- CORS is restricted to the configured `FRONTEND_ORIGINS`.

Production example:

```env
APP_ENV=production
API_KEY=<strong-random-secret>
DOCS_ENABLED=false
TRUSTED_HOSTS=<api-domain>
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_FAIL_CLOSED=true
FRONTEND_ORIGINS=https://<frontend-domain>
```

The API should be served behind HTTPS. `Strict-Transport-Security` is enabled by default for production responses.

For API clients, send the API key as:

```http
X-API-Key: <strong-random-secret>
```

Do not use a source-control value for `API_KEY`. Generate a new high-entropy secret and store it only in FastAPI Cloud or the deployment secret manager.
