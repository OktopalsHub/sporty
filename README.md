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
