## [mongo-postgres-backend] Added PostgreSQL read APIs for POIs
- Codebase/domain discoveries: The configured PostgreSQL database was reachable; read-only catalog inspection found existing `pois`, `poi_localizations`, and `poi_images` tables, but no deleted-POI tombstone table. The user-provided worktree already included a PostgreSQL health-only `main.py` plus legacy Mongo route/service files.
- Wrong assumptions and corrections: PostgreSQL health success did not mean the Mongo business APIs had been migrated. The live schema contained zero active POIs, so valid-record detail behavior was tested with a mocked session instead.
- Debugging dead-ends and what actually worked: `Annotated[AsyncSession, get_db]` is not a FastAPI dependency; use `Depends(get_db)`. A `Response` return annotation is needed for an endpoint returning either JSON or 304 responses. Pointing routes at `app.postgres.get_db` avoids creating a second engine.
- Techniques/patterns worth reusing: Use `SET TRANSACTION READ ONLY` for catalog inspection and only `SELECT`-based live probes; store images in `poi_images`, and join localization fallback rows rather than expecting Mongo-shaped embedded arrays. Current sync cursors are Unix microseconds and deletion tombstones remain unsupported.
- Learnings consumed: [(none)]

## [mongo-postgres-audio] Migrated audio/localization/map services to PostgreSQL
- Codebase/domain discoveries: `audio_tasks` requires both POI and localization UUID foreign keys; `poi_localizations` has a unique `(poi_id, language_code)` constraint; the only existing rate log is `localization_request_logs`; published pack assets are in `offline_pack_assets`.
- Wrong assumptions and corrections: There is no `rate_limits`, `meta`, or `deleted_pois` table. Rate-limit writes use JSONB metadata in localization request logs; sync versioning uses `pois.updated_at`, and deleted-POI tombstones remain unsupported.
- Debugging dead-ends and what actually worked: Schema inspection imports the configured engine only when the process runs from `backend/` so Pydantic loads its local env file. One initial query output hit Windows console encoding; setting `PYTHONIOENCODING=utf-8` fixed display without reading or printing credentials.
- Techniques/patterns worth reusing: Background audio workers must store the `AsyncSessionLocal` factory, not a request-scoped `AsyncSession`. Keep status translation at the persistence/API boundary, use mocks for writes, and do not create indexes at runtime when DDL is prohibited.
- Learnings consumed: [backend/postgres-read-api]

## [poi-postgres-workflows] Migrated POI geo, admin, and owner workflows
- Codebase/domain discoveries: `owner_registrations` references `users.id` and stores submitted metadata as JSONB with encrypted verification bytes; submissions and notifications are UUID-linked to users. The POI schema requires category/address defaults absent from legacy request models.
- Wrong assumptions and corrections: Physical POI deletion is unsafe for existing relational references and cannot preserve Mongo tombstones; archive rows instead. `menus`/`menu_items` have no corresponding routes in the scoped legacy modules.
- Debugging dead-ends and what actually worked: Focused fake-session tests avoid touching live DB state. The repository-level `tests/conftest.py` includes Mongo connection/deletion behavior; skip it for owner unit validation with `--noconftest`.
- Techniques/patterns worth reusing: Resolve auth identities from UUID claims first, then `users.email`; use bound SQL, JSONB casts, and row locks for owner review and image count operations.
- Learnings consumed: [backend/postgres-read-api]

## [mongo-postgres-auth-backend] Ported auth, permissions, audit and admin metadata
- Codebase/domain discoveries: The actual schema uses `users.email` as the login identifier, stores role/permission grants in many-to-many relationship tables, and supports stateful revocation through `auth_sessions`. `audit_logs` has JSONB and INET fields usable for durable failed-login/success markers; no `rate_limits` table exists.
- Wrong assumptions and corrections: There is no `username` or role `priority` column and no persisted password-session version column; preserve the API `username` key as email, report unavailable priority as `null`, and revoke existing auth sessions on password changes.
- Debugging dead-ends and what actually worked: Inspected column metadata and constraints in an explicit `READ ONLY` transaction; tests use a fake `AsyncSession` because the task prohibits live database writes. A broad fake-session SQL matcher confused the user-permission join with user lookup; narrowing it to the selected user columns fixed the fixture. `ruff` flagged inline `Depends(get_db)` defaults, so dependencies share a module-level alias.
- Techniques/patterns worth reusing: Keep JWT permissions fresh by querying PostgreSQL grants; persist only SHA-256 refresh-token digests, bind JWTs to `auth_sessions.id`, and logically reset append-only login throttle windows with success events instead of deleting audit rows.
- Learnings consumed: [backend/postgres-read-api]

## [analytics-postgres-backend] Migrated analytics, runtime observability, and AI usage
- Codebase/domain discoveries: Analytics consent status is constrained to granted/denied/withdrawn; event rows require a consent FK but have no session id or pre-aggregated model. Runtime metric buckets have a unique dimensions key, and AI daily usage has a unique user/date key.
- Wrong assumptions and corrections: Existing Mongo `analytics_sessions`/dashboard read models are not in the PostgreSQL schema. Session counts must be reported as unavailable rather than fabricated; live event queries replace the absent read model.
- Debugging dead-ends and what actually worked: `ruff format --check` initially hit a formatter bug on the admin router; running Ruff format on that file resolved the check. Focused API tests use dependency overrides and never connect for writes.
- Techniques/patterns worth reusing: Serialize consent upserts with a PostgreSQL advisory lock where the existing table lacks a unique visitor constraint; use an atomic conditional `ON CONFLICT` update for daily quotas. Process-local presence/rate limits avoid Redis but reset on restart and do not coordinate across workers.
- Learnings consumed: [backend/postgres-read-api]
