# Audio, Localization, and Map-Pack PostgreSQL Migration

## Summary

Migrated the assigned audio, localization, warmup, map audio-pack, sync, and rate-limit paths to `AsyncSession` from `app.postgres` and the existing PostgreSQL schema. No routers were mounted in `main.py`; the exported router objects remain `audio.router`, `localizations.router`, `warmup.router`, and `maps.router`.

## Implementation

- Replaced Mongo access in the four assigned routers and six assigned services with parameterized SQLAlchemy statements and existing PostgreSQL relations.
- Used `audio_tasks` plus its existing localization/POI foreign keys for durable task state; API task statuses are mapped to the existing status constraint.
- Upserted translations on the existing unique `(poi_id, language_code)` constraint and wrote localization request/rate-limit records to `localization_request_logs`.
- Read audio pack manifests from published `offline_packs` and matching `offline_pack_assets`.
- Kept auth dependencies unchanged. The localization route records translation metadata in `localization_request_logs`; `audit.py` was not changed.
- Added mock-backed endpoint/service tests in `backend/tests_postgres/test_audio_localization_migration.py`.

## Existing Schema and Constraints

Read-only inspection used `SET TRANSACTION READ ONLY` and SELECTs against `information_schema`, `pg_constraint`, and `pg_indexes`; no DDL or data mutation was executed.

- `poi_localizations` has a unique `(poi_id, language_code)` constraint and audio/readiness status checks.
- `audio_tasks` requires UUID `poi_id` and `localization_id` foreign keys; statuses are `queued`, `processing`, `completed`, `failed`, `paused`, and `cancelled`; progress is constrained to 0–100.
- `offline_pack_assets` supports `audio` assets and references `offline_packs`; only `published` packs are included in audio-pack results.
- `localization_request_logs` has an optional `user_id`, `operation`, `requested_at`, `was_allowed`, and JSONB `request_metadata`.
- There are no `rate_limits`, `meta`, or `deleted_pois` relations in the inspected schema.

## Unsupported or Changed Behavior

- POI IDs in the migrated audio/localization routes must be PostgreSQL UUIDs; legacy Mongo ObjectId values are no longer accepted.
- A task cannot be persisted without an existing localization row because `audio_tasks.localization_id` is non-null and FK-constrained. Audio activation skips requested languages that lack such a row rather than creating an invalid/failed task.
- Rate-limit records are stored in `localization_request_logs` JSONB metadata because the schema has no `rate_limits` table. The existing indexes do not include the rate-limit key/path fields, so this query has no dedicated composite index.
- Generic Mongo `audit_logs` writes are not reproduced; translation events are stored as `poi:translate` localization-request log rows because `audit.py` is explicitly out of scope.
- `maps/audio-pack` reports only published audio assets and returns each existing `storage_key` as `url`; no public-URL column exists in the inspected schema.
- `cham_dataset` now returns the active-POI `updated_at` microsecond cursor rather than incrementing a persistent counter. `ghi_mo_xoa` raises `NotImplementedError` because no deletion-tombstone table exists. Delta deletion parity is unsupported.
- The routers are intentionally not mounted in the application. Runtime checks exercised the changed endpoints in isolated FastAPI test apps with mocked database sessions.

## Upstream Artifacts Consumed

- `.github/modernize/rearchitecture/artifacts/mongo-postgres-backend.md` — prior PostgreSQL migration summary and schema context.

## Evidence Mapping

- `mongo-postgres-backend.md#Existing Schema Inspected` → this artifact’s read-only schema/constraint inspection and table mappings.
- `mongo-postgres-backend.md#Contract and Limitations` → this artifact’s explicit cursor and tombstone limitations.
- Current `pg_constraint`/`pg_indexes` SELECT results → the relation constraints and rate-limit index limitation listed above.

## Test Results

- Command: `Set-Location backend; .\.venv\Scripts\python.exe -m pytest -q tests_postgres\test_audio_localization_migration.py`
- Passed: 13
- Failed: 0
- Skipped: 0
- Failure details: none.
- Lint: `ruff check` on the 10 scoped production files and the new test file — passed.
- Format: `ruff format --check` on the same files — passed.
- Full PostgreSQL-focused suite command: `Set-Location backend; .\.venv\Scripts\python.exe -m pytest -q tests_postgres`
- Full-suite result: 42 passed, 4 failed, 0 skipped; the four failures are in the concurrent auth worker’s `tests_postgres/test_auth_postgres.py` tests and concern permission retrieval/UUID serialization/role authorization. They are outside this task’s allowed edit scope and are escalated separately.
- Failure details: `test_login_me_refresh_and_logout_use_postgres_session` and `test_unknown_role_returns_no_permissions_and_seed_helper_does_not_mutate` fail because permission lookup returns a user row; `test_password_change_revokes_old_session_and_reissues_current_session` fails on a UUID JWT claim serialization error; `test_meta_routes_and_audit_helper_use_existing_relations` receives 403 instead of 200 for `/admin/roles`.
- Warning: one Starlette `httpx` deprecation warning.
