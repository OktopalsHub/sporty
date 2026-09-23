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
