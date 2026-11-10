# MongoDB → PostgreSQL Auth Migration — Backend

## Summary

Ported authentication, permission lookup, audit writes/reads, admin auth/meta routes, and failed-login throttling to the existing PostgreSQL schema. `main.py` was not changed; the parent must mount the two routers noted below.

## Implemented

- `auth.py` resolves login identifiers against `users.email`, loads a compatibility role through `user_roles`/`roles`, unions the user's current grants from `role_permissions`/`permissions`, and uses `auth_sessions` for refresh-token hashes, expiry, logout revocation, and password-change revocation.
- `admin_auth.py` retains login, `/me`, refresh, logout, and password-change behavior; login responses continue to expose the `username` field, whose value maps to the existing email identifier.
- `permissions.py` reads stored grants. `dam_bao_roles` is a read-only compatibility check and does not seed roles.
- `audit.py` writes to existing `audit_logs`; `admin_meta.py` reads role grants and the latest 100 audit records. Role `priority` is `null` because the schema has no priority column.
- `login_guard.py` replaces Mongo `rate_limits` documents with failed-login and success-marker events in `audit_logs`, using the existing JSONB and INET fields. No new table or index is required.
- Migrated auth modules use `app.postgres` and `app.core.config`; they do not import Mongo/Motor modules or the legacy Mongo settings.

## Routers for Parent to Mount

- `app.routers.admin_auth.router` — includes `/admin/auth/login`, `/admin/auth/me`, `/admin/auth/refresh`, `/admin/auth/logout`, and `/admin/auth/change-password`.
- `app.routers.admin_meta.router` — includes `/admin/roles` and `/admin/audit-logs`.

Both routers already define their prefixes; mount them directly with `app.include_router(...)`.

## Existing Schema Inspection

Inspected the connected PostgreSQL catalog in transactions explicitly set `READ ONLY`, querying only `information_schema` and catalog constraint metadata. No application rows were queried, and no DDL or data mutation was run during inspection.

- `users`: UUID id, unique email, password hash, account status (check permits `active`), and owner verification timestamp.
- `roles.code` and `permissions.code` are unique; `user_roles` and `role_permissions` are composite-key relationship tables.
- `auth_sessions`: UUID id, user id, unique refresh-token hash, IP, expiry, and revocation timestamp. Its check requires expiry after creation.
- `audit_logs`: generated identity id, nullable actor UUID, action/resource fields, JSONB before/after data, INET address, and `created_at`.
- No `rate_limits` table exists in the inspected schema.

The migration and its focused tests did not write to the live database. Runtime endpoints will write session/audit records when mounted and invoked.

## Unported Dependencies and Limits

- `main.py` remains unchanged, so the routes are not mounted by this task.
- Legacy Mongo files (`app/db.py`, `app/database.py`, and `app/main mongo.py`) and Motor/PyMongo requirements remain for other legacy paths; they are not imported by the migrated modules.
- The legacy `username` field is represented by `users.email`; role priority is unavailable in the existing schema.
- The login throttle now records durable audit events instead of deleting rate-limit documents. Existing audit history is append-only; a success event resets each username/IP window logically.

## Upstream Artifacts Consumed

- `.github/modernize/rearchitecture/artifacts/mongo-postgres-backend.md` — prior migration scope and confirmation that auth/admin behavior remained unported.
- `.github/modernize/rearchitecture/learnings/backend/postgres-read-api.md` — reuse the PostgreSQL engine/session and inspect schema read-only.

## Evidence Mapping

- `mongo-postgres-backend.md#Contract and Limitations` → this migration adds the previously unported auth/admin scope; focused router tests exercise the new routes.
- `postgres-read-api.md#Takeaway` → all migrated database operations use the existing PostgreSQL session/schema; schema evidence above records the read-only inspection.

## Test Results

- Command: `.\.venv\Scripts\python.exe -m pytest -q tests_postgres\test_auth_postgres.py` (working directory: `backend`)
- Passed: 5
- Failed: 0
- Skipped: 0
- Failure details: none. Tests use a fake `AsyncSession`; they do not mutate the live database.
- Runtime route coverage: login, `/me`, refresh, logout, password change/session revocation, `/roles`, and `/audit-logs`; valid responses returned 2xx and revoked/invalid tokens returned 401.
- Lint: `.\.venv\Scripts\python.exe -m ruff check app\auth.py app\permissions.py app\audit.py app\services\login_guard.py app\routers\admin_auth.py app\routers\admin_meta.py app\core\config.py tests_postgres\test_auth_postgres.py` — passed.
- Format: `.\.venv\Scripts\python.exe -m ruff format --check app\auth.py app\permissions.py app\audit.py app\services\login_guard.py app\routers\admin_auth.py app\routers\admin_meta.py app\core\config.py tests_postgres\test_auth_postgres.py` — passed.
- Syntax: `.\.venv\Scripts\python.exe -m compileall -q app\auth.py app\permissions.py app\audit.py app\services\login_guard.py app\routers\admin_auth.py app\routers\admin_meta.py app\core\config.py tests_postgres\test_auth_postgres.py` — passed.
- Test warning: installed Starlette emits a deprecation warning about its `httpx` TestClient integration; it did not fail tests.
