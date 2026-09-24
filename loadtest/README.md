# Phase 23 load and reliability tests

These tests measure the API under concurrent HTTP load without sending a large number of real SportyBet prediction requests.

## Install

```bash
pip install -e ".[dev,loadtest]"
```

## Local target

Start the production-like stack first:

```bash
docker compose up --build -d
```

Run a short headless test:

```bash
locust -f loadtest/locustfile.py --headless -u 25 -r 5 -t 60s
```

Run a larger local test:

```bash
locust -f loadtest/locustfile.py --headless -u 100 -r 10 -t 5m
```

For production-like API-key protection:

```bash
LOADTEST_API_KEY="$API_KEY" locust -f loadtest/locustfile.py --headless -u 100 -r 10 -t 5m
```

Never point these tests at production unless an explicit load-test window and a safe request budget have been approved.

## What to record

For each run record:

- concurrent users
- spawn rate
- requests per second
- total requests
- failures and HTTP status codes
- p50, p95, p99 latency
- PostgreSQL active connections and pool exhaustion
- Redis connected clients and command latency
- prediction queue depth
- worker job duration, retry count, and failure count

The baseline health/readiness profile is intentionally cheap. Business endpoints should be tested separately with a staging SportyBet feed or mocked provider so an HTTP load test does not create uncontrolled upstream traffic or prediction jobs.

## Reliability checks

During a staging run, verify all of the following:

1. The API stays responsive while the worker processes jobs.
2. Redis rate limiting is shared across API instances.
3. PostgreSQL connection counts remain within the Neon plan limit.
4. Queue depth drains after load stops.
5. Duplicate workers do not process the same job concurrently.
6. Failed jobs retry up to the configured limit and then become `failed`.
7. A Redis restart causes readiness to fail and rate limiting to fail closed when configured.
8. API instances can restart without losing database-backed job state.

## Suggested baseline

Use the local Docker stack for the first baseline:

| Test | Users | Spawn | Duration | Purpose |
| --- | ---: | ---: | ---: | --- |
| Smoke | 5 | 1/s | 30s | Basic availability |
| Baseline | 25 | 5/s | 60s | Normal concurrency |
| Sustained | 100 | 10/s | 5m | Pool and Redis stability |
| Spike | 250 | 50/s | 60s | Recovery after rapid concurrency growth |

These are test inputs, not production SLOs. Set final SLOs after measuring the actual deployment and database/Redis plan limits.
