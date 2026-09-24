# Phase 25 release automation

Phase 25 makes production deployment depend on a successful CI run and prevents overlapping production deployments.

## Release flow

~~~text
Pull request
   |
   v
CI
   |
   | merge to main
   v
CI on main
   |
   | success
   v
Production deployment
   |
   +--> Alembic migrations -> Neon
   |
   +--> FastAPI Cloud deploy
~~~

## Changes

- CI has read-only repository permissions.
- CI runs have a 15 minute timeout.
- Older CI runs for the same ref are cancelled when a newer run starts.
- Production deployment waits for the `CI` workflow on `main` to complete successfully.
- The deployment checks out the exact commit that passed CI.
- Production deployments use a single concurrency group, so two deployments cannot run at the same time.
- The production deployment has a 20 minute timeout.
- The deployment uses the GitHub `production` environment.
- Required deployment secrets are checked before migrations run:
  - `DATABASE_URL`
  - `FASTAPI_CLOUD_TOKEN`
  - `FASTAPI_CLOUD_APP_ID`
- Manual deployment remains available through `workflow_dispatch`.

## Required GitHub configuration

Create a GitHub environment named `production`.

Add these secrets to the environment:

- `DATABASE_URL`
- `FASTAPI_CLOUD_TOKEN`
- `FASTAPI_CLOUD_APP_ID`

Environment protection rules can be used to require an approval before a production deployment.

## Important migration rule

The deployment workflow still runs:

~~~bash
alembic upgrade head
~~~

before `fastapi deploy`.

Database migrations must remain backward compatible with the application version already running during a rolling deployment.

## Manual release

The workflow can still be started manually from GitHub Actions. A manual run deploys the selected workflow revision.

## Verification

Before enabling automatic production deployment:

1. Confirm the `CI` workflow is required for the main branch.
2. Create the `production` environment.
3. Add the three required secrets.
4. Add an approval rule if manual production approval is required.
5. Run CI on a test change.
6. Merge only after CI succeeds.
7. Confirm the production deployment checks out the same tested commit.
8. Confirm migrations complete before the FastAPI Cloud deployment starts.
