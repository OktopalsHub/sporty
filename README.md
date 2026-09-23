# Sporty

AI-powered football prediction and SportyBet ticket builder.

## Development

FastAPI backend with isolated provider adapters, prediction strategies, ticket generation, and persistent selection history.

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

Database tables are initialized when the application starts.

## Phase 11 endpoints

- `POST /api/v1/selections/sessions` creates a persistent selection session.
- `GET /api/v1/selections/sessions/{session_id}` restores selections from the database.
- `POST /api/v1/tickets/{session_id}/build` builds the exact selected ticket and records a successful build.
- `GET /api/v1/history/tickets/{session_id}` returns previous successful ticket builds for a session.


## Database migrations

Phase 12 uses Alembic for schema management. The application no longer creates tables automatically at startup.

After installing dependencies, run:

```bash
alembic upgrade head
```

If you already have a Phase 11 database created with `create_all`, verify that its schema is current and then mark the initial migration as applied instead of recreating the tables:

```bash
alembic stamp 0001_initial
```

For MySQL, set `DATABASE_URL` first:

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/sporty
```

Create a new migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

The API exposes `GET /api/v1/health` for liveness and `GET /api/v1/ready` for database readiness.

Every API response includes an `X-Request-ID` header. Clients may send their own request ID for tracing.


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
