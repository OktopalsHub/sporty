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

The application uses SQLAlchemy.

For local development:

```env
DATABASE_URL=sqlite:///./sporty.db
```

For MySQL:

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/sporty
```

The application does not create tables automatically at startup. Use Alembic to apply the schema before starting the API:

```bash
alembic upgrade head
```

If you already have a Phase 11 database created with `create_all`, verify that its schema matches the migration and then mark the initial migration as applied:

```bash
alembic stamp 0001_initial
```

Create a new migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## API health

- `GET /api/v1/health` is the liveness check. It does not require the database.
- `GET /api/v1/ready` is the readiness check. It verifies database connectivity.
- Every API response includes an `X-Request-ID` header. Clients may send their own request ID for tracing.

## Docker

Build and run the production-like image:

```bash
docker build -t sporty .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=sqlite:///./sporty.db \
  sporty
```

For a MySQL-backed local stack:

```bash
docker compose up --build
```

The container entrypoint runs `alembic upgrade head` before starting Uvicorn. Production deployments should use the same migration-first pattern and provide secrets through the deployment environment, not the image.

## Phase 13 frontend integration contract

The backend exposes a stable frontend-facing contract through FastAPI OpenAPI and a metadata endpoint.

### Bootstrap

- `GET /api/v1/meta` returns the supported markets and ticket strategies.
- `GET /api/v1/health` is the liveness check.
- `GET /api/v1/ready` is the database readiness check.
- The API returns `X-Request-ID` on every response. A frontend can send the same header when tracing a request.

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

Set `FRONTEND_ORIGINS` to a comma-separated list of allowed frontend origins:

```env
FRONTEND_ORIGINS=http://localhost:3000,http://localhost:5173
```

FastAPI OpenAPI is available at `/docs` and `/openapi.json` for frontend client generation.

## CI

GitHub Actions runs on pushes and pull requests. It installs the development dependencies, runs Ruff, runs the test suite with coverage, and applies the Alembic migrations against SQLite.

The CI workflow is the minimum merge gate. A deployment should also run the same migration command against the target database before serving traffic.
