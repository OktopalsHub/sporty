# Phase 26 production verification

Phase 26 adds a repeatable smoke test for a deployed production API.

## What it checks

The manual GitHub Actions workflow checks:

1. Public liveness returns `status=ok`.
2. Public readiness returns `status=ready`.
3. A protected API endpoint rejects a request without `X-API-Key`.
4. The same endpoint works with the production API key.
5. The API documentation endpoint returns 404 when docs are disabled.

## Required GitHub configuration

The workflow uses the existing `production` environment.

Add this environment secret:

- `API_KEY`: the same production API key configured on the deployed API.

Do not put the API key in workflow inputs or command arguments. The workflow reads it from the protected GitHub environment.

## Run the verification

Open GitHub Actions and select **Production verification**.

Provide:

```text
base_url=https://<production-api-host>
verify_docs_disabled=true
```

The workflow uses retries for the public health checks and fails if any expected response is missing.

## Release sequence

The recommended production sequence is:

```text
Merge to main
    |
    v
CI
    |
    v
Phase 25 production deployment
    |
    +--> migrations
    |
    +--> FastAPI Cloud deployment
    |
    v
Phase 26 production verification
    |
    +--> health
    +--> readiness
    +--> API key rejection
    +--> authenticated API
    +--> docs exposure
```

## Rollback

If verification fails:

1. Stop further production releases.
2. Check the failed verification step and FastAPI Cloud logs.
3. Check Logfire traces for the failing request.
4. Check Neon migration status if the failure started after a schema change.
5. Check managed Redis connectivity if readiness or protected requests fail.
6. Roll back the application using the deployment platform's previous release mechanism when the failure is application-level.
7. Do not manually reverse a database migration unless a tested rollback migration exists.

Database migrations must remain backward compatible with the previous application version because production deployments can overlap during rolling replacement.

## Success criteria

A production release is operationally verified when:

- health is OK;
- readiness reports ready;
- unauthenticated protected API requests return 401;
- authenticated API requests return successfully;
- disabled documentation is not exposed when configured;
- no new application errors are visible in Logfire;
- worker and queue health are confirmed separately when background jobs are enabled.

The workflow is a smoke test, not a full load or business-logic test.
