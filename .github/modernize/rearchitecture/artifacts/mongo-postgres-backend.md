# MongoDB to PostgreSQL Backend Migration — Backend

## Summary

The running FastAPI app now uses the existing PostgreSQL connection for health checks and read-only POI APIs, and serves the existing static UI bundles. No database schema or row was modified.

## Implemented

- Mounted PostgreSQL-backed routes for `GET /poi`, `GET /poi/{id}`, `GET /poi/load-all`, `GET /poi/delta`, `GET /poi/nearby`, and `GET /poi/hotset`.
- Read POI/localization/image records from existing `pois`, `poi_localizations`, and `poi_images` tables using parameterized SQLAlchemy queries.
- Mounted the existing static `/ui-bundles/{locale}` route; it reads files and does not use MongoDB.
- Updated the root and backend READMEs with current runtime scope and limitations.
- Added six unit tests for the PostgreSQL POI API.

## Existing Schema Inspected

Schema discovery used a PostgreSQL `READ ONLY` transaction over `information_schema`. The connected database had 28 user-visible base tables, including `pois`, `poi_localizations`, `poi_images`, `content_dataset_versions`, `users`, `roles`, `analytics_events`, `audio_tasks`, and `owner_registrations`. The API queries only the existing POI/localization/image tables. No `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `INSERT`, `UPDATE`, or `DELETE` was executed during this task.

## Contract and Limitations

- `version`/`sync_cursor` is a Unix-epoch microsecond cursor derived from `pois.updated_at`, rather than the old Mongo counter. Clients should treat it as an opaque integer and send it back as `updated_after`.
- The existing schema has no deleted-POI tombstone table. `removed_poi_ids` is therefore always empty; deletion delta parity is unsupported.
- PostgreSQL has no Mongo-style `images` array on `pois`; image URLs are read from `poi_images`.
- Public routes include rows marked `is_active = true`. No change/write/admin routes were mounted.
- Admin/auth, owner workflows, analytics ingestion/dashboard/workers, AI usage limits, audio generation/task controls, localization writes, Mongo rate limits, and other Mongo-backed routes/services remain unimplemented and unmounted. This is a partial migration, not full API parity.
- The runtime smoke found zero active POIs, so a valid-record detail response could not be exercised against live data; detail behavior is covered by a mocked unit test.

## Upstream Artifacts Consumed

none — no dependency artifacts provided; the expected `.github/modernize/rearchitecture` context and artifacts directory did not exist.

## Evidence Mapping

none — no dependency artifacts provided. Existing database schema evidence is summarized above; API behavior is verified below.

## Test Results

- Command: `backend\.venv\Scripts\python.exe -m pytest -q tests_postgres\test_poi_api.py`
- Passed: 6
- Failed: 0
- Skipped: 0
- Failure details: none.
- Lint: `ruff check app\api\pois.py app\main.py tests_postgres\test_poi_api.py` — passed.
- Format: `ruff format --check app\api\pois.py app\main.py tests_postgres\test_poi_api.py` — passed.
- Runtime smoke: read-only GET probes to `/`, `/api/v1/health/database`, `/poi`, `/poi/load-all`, `/poi/delta?updated_after=0`, `/poi/nearby`, `/poi/hotset`, and `/ui-bundles/en` all returned 200. No active POIs existed for a live detail probe.
- Legacy MongoDB suite: not run; its shared fixture deletes `rate_limits`, and the task prohibits modifying existing database data.
