# Analytics, Runtime Observability, and AI — PostgreSQL Backend

## Summary

Migrated the scoped analytics, runtime-observability, and AI request paths to `AsyncSession` / `get_db` from `app.postgres`. This task leaves `main.py` unchanged; router exports are listed for later mounting. The `presence` service no longer needs Redis or MongoDB; route-level rate limits and the five-minute presence window now use bounded process-local memory.

Router exports for later mounting:

- `app.routers.analytics.router`
- `app.routers.admin_analytics.router`
- `app.routers.runtime_observability.router`
- `app.routers.ai.router`

## Schema Evidence

Inspected the existing schema using `information_schema`, `pg_constraint`, and `pg_indexes` in a `SET TRANSACTION READ ONLY` transaction. No DDL or data mutation was performed.

- `analytics_consents` requires `anonymous_visitor_id`, `consent_status`, and `policy_version`; its status check permits `granted`, `denied`, and `withdrawn`. Consent writes use `granted` / `withdrawn`, and the API continues returning legacy `revoked` for non-granted states. The table has no unique visitor constraint, so writes serialize by PostgreSQL advisory lock.
- `analytics_events` requires a consent FK and stores `event_properties` as JSONB. It has no `session_id`, pre-aggregated daily/hourly table, or worker/job table. Dashboard metrics therefore query the event table for bounded date ranges; session counts cannot be reconstructed.
- `ai_usage_daily` has a unique `(user_id, usage_date)` constraint, nonnegative counters, and a user FK. The owner quota uses an atomic upsert guarded by the existing daily limit.
- `ai_advisor_requests` allows `pending`, `completed`, `failed`, and `timeout`; request records use those statuses and store elapsed time. The provider interface returns text only, so input/output token counts remain unavailable.
- `runtime_observability_hourly` has a unique `(bucket_start, metric_name, metric_dimensions)` constraint and nonnegative `sample_count`; writes upsert rounded cell/outcome counters against that key.
- `users.owner_verified_at` supports the existing verified-owner gate. `audit_logs` was inspected but is not written by these endpoints.

## Behavior and Known Limitations

- Analytics event collection continues to require both a valid signed receipt and a current granted consent. Sensitive event property keys are dropped before JSONB storage.
- `sessions_today` is returned as `null` with `sessions_available: false`, because the existing analytics schema stores no session identifier. `devices_today` is a distinct visitor count.
- Runtime location remains separate from consent-gated analytics; coordinates are rounded and grouped into hourly cells, and client-supplied environment fields are discarded.
- Presence and rate limits are process-local, reset on restart, and are not shared across multiple workers or replicas. This avoids adding Redis but is not a distributed limiter.
- AI owner identity resolution accepts `id`/`user_id`, or falls back to `email`/`username` matching `users.email`. The parallel auth migration must expose a compatible PostgreSQL identity for verified-owner checks and quotas.
- AI request tokens/model name are unavailable from the current provider interface; corresponding nullable schema columns are not populated. Provider error text is not stored; only the exception class is recorded.
- Existing authentication and `analytics:view` permission dependencies were retained. This task did not edit auth, permissions, audit, connection/config, or application mounting files.

## Upstream Artifacts Consumed

- `.github/modernize/rearchitecture/artifacts/mongo-postgres-backend.md` — prior migration state and confirmation that these analytics/admin paths were previously outside the mounted PostgreSQL API scope.
- `.github/modernize/rearchitecture/learnings/backend/postgres-read-api.md` — reuse the application PostgreSQL dependency and avoid schema changes.
- No task dependency artifacts were provided.

## Evidence Mapping

- `mongo-postgres-backend.md#Contract and Limitations` → this migration stays within the existing tables and does not claim unsupported session/read-model parity.
- `postgres-read-api.md#Takeaway` → SQL uses the application `AsyncSession` dependency and no request-time index/DDL creation; verified by focused tests and scoped source checks.
- Read-only catalog inspection of the named tables → `Schema Evidence` above and parameterized PostgreSQL statements covered by mocked-session tests.

## Test Results

- Command: `backend\.venv\Scripts\python.exe -m pytest -q tests_postgres\test_analytics_postgres.py` (run from `backend`)
- Passed: 12
- Failed: 0
- Skipped: 0
- Failure details: none. Tests use mocked SQL sessions and FastAPI dependency overrides; no test writes to a real database.
- Lint: `ruff check` on the 10 changed Python files — passed.
- Format: `ruff format --check` on the 10 changed Python files — passed.
- Runtime API probes: analytics consent GET/POST and collect POST; runtime location POST; admin analytics summary and runtime window GET; AI description POST all returned 200 under mocked dependencies.
