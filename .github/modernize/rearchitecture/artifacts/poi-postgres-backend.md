# PostgreSQL POI, Geo, Admin, and Owner Routes

## Summary

Converted the scoped public POI export, geospatial queries, admin POI/image operations, and owner registration/submission/notification flows to SQLAlchemy `AsyncSession` queries against the existing PostgreSQL schema. No schema or live data was changed during inspection or testing.

## Router Exports

- `app.routers.poi.router` — compatibility alias for `app.api.pois.router`, the existing PostgreSQL public list/detail/sync/geo routes.
- `app.routers.geo.router` — PostgreSQL `/poi/nearby` and `/poi/hotset`.
- `app.routers.admin_pois.router` — admin POI CRUD and image endpoints.
- `app.routers.owner.router` — owner registration, review, submission, and notification endpoints.

The current `main.py` already includes `app.api.pois.router`. Do not mount both that router and `app.routers.poi.router`; they are the same router object. Its routes already include nearby/hotset, so also avoid mounting `app.routers.geo.router` alongside it unless the existing public router is removed. Parent integration should add the admin and owner exports.

## Behavior and Schema Mapping

- User identity maps to `users.id` and `users.email`; owner submissions and notifications use the UUID `owner_id`.
- Registration stores the encrypted verification value in `owner_registrations.verification_data_enc` and non-sensitive login identity in `submitted_data`.
- Owner edits map to `poi_submissions.content_snapshot` and the schema's `create`/`update` submission types. Approval updates or creates a POI, marks it inactive pending review, and creates an `owner_notifications` row.
- POI image URLs and metadata use `poi_images`; local image files retain the existing safe UUID filename and validation helpers.
- Admin deletion archives the row (`is_active = false`, `publication_status = 'archived'`) rather than hard-deleting records referenced by submissions or other tables.
- New POIs use `category = 'other'`, empty `address_line`, and draft/inactive state because the legacy request model contains no category/address fields.
- Geo distance/radius searches use parameterized PostGIS `ST_Distance` and `ST_DWithin`.

## Limitations

- The schema has no deleted-POI tombstone table. Admin deletes are soft archives; removal IDs cannot be emitted by the existing delta API.
- The POI schema has no audio task/status columns or audio queue table. Legacy audio generation triggers cannot be invoked from the migrated routes.
- The owner registration API still accepts the legacy `username` field, which is mapped to `users.email`; clients should provide the same login identifier used by PostgreSQL auth.
- Approval assigns the `poi_owner` role only when that role code exists in `roles`.
- No legacy admin menu endpoints existed in the scoped router. `menus` and `menu_items` remain unused by this migration.
- `doc_cccd` now requires an `AsyncSession`; there were no repository call sites for its former Mongo-global session form.
- Full runtime behavior with real auth/provider state was not tested. Route tests use fake sessions and do not write to the connected database.

## Upstream Artifacts Consumed

- `.github/modernize/rearchitecture/artifacts/mongo-postgres-backend.md` — current PostgreSQL public-read API and missing tombstone behavior.
- `.github/modernize/rearchitecture/learnings/backend/postgres-read-api.md` — connection and read-only schema inspection conventions.

## Evidence Mapping

- `mongo-postgres-backend.md#Contract and Limitations` → public router alias, PostGIS query implementation, no-tombstone handling, and delta limitation described above.
- `postgres-read-api.md#Takeaway` → the existing `get_db`/`AsyncSession` pattern and read-only schema inspection approach.
- Read-only schema inspection (`information_schema.columns` and `pg_constraint`) → SQL uses only existing columns and observed FK/check constraints; no DDL or data mutation was issued.

## Test Results

- Command: `backend\.venv\Scripts\python.exe -m pytest -q tests_postgres\test_poi_api.py tests_postgres\test_poi_write_workflows.py`
- Passed: 16
- Failed: 0
- Skipped: 0
- Command: `backend\.venv\Scripts\python.exe -m pytest --noconftest -q tests\test_owner.py`
- Passed: 2
- Failed: 0
- Skipped: 0
- Command: Ruff check and `ruff format --check` on the changed routers, helper, and tests
- Result: passed.
- Command: `python -m compileall -q` on changed Python files
- Result: passed.
- Broader command: `python -m pytest -q tests_postgres tests\test_owner.py`
- Result: 34 passed, 2 failed; it also encountered an unavailable local MongoDB fixture. The reported failing assertions were in unrelated analytics PostgreSQL tests (including `test_summary_uses_events_and_exposes_unavailable_session_count`, which expected `sessions_today is None` but received `0`). No scoped POI workflow test failed. The Mongo fixture could not connect to localhost; no live PostgreSQL mutation was performed.
