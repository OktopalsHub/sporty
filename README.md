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

Redis is used for distributed API rate limiting.

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

The container entrypoint runs `alembic upgrade head` before starting Uvicorn. Production deployments should use the same migration-first pattern and provide secrets through the deployment environment, not the image.

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
