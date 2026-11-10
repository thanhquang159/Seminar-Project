# PostgreSQL Read API

For this project, keep the first PostgreSQL route migrations read-only and use SQLAlchemy async sessions against the existing schema instead of creating parallel tables.

## What Happened

For `Seminar-Project/mongo-postgres-backend`, schema inspection found existing POI, localization, and image tables. New routes use bound SQL parameters and `AsyncSession`; existing Mongo routes remain unmounted until their contracts and all dependent tables are migrated. The schema has no deleted-POI tombstone, so delta cannot report removals.

## Takeaway

Inspect `information_schema` inside a read-only transaction before writing route SQL. Use `updated_at` as an opaque high-resolution sync cursor only when a counter table is absent, document its units, and never imply delete-delta parity without an existing tombstone source. Reuse the application engine's `get_db` dependency so startup/shutdown owns one pool.

## Write Workflow Mapping

The existing schema maps owner login identifiers to `users.email`, owner state to UUID-keyed registration/submission/notification tables, and sensitive verification bytes to `owner_registrations.verification_data_enc`. Admin POI deletion should archive rows rather than hard-delete relationally referenced records. The scoped POI schema has no audio task/status table, so legacy audio triggers cannot be preserved.

Use the existing `AsyncSession` transaction for related updates, lock registration/submission rows while reviewing, and store JSON snapshots with bound parameters cast to JSONB. Populate required POI category/address columns with documented defaults when the request contract lacks those fields.

## History

- 2026-11-09 (Seminar-Project/mongo-postgres-backend): initial
- 2026-11-09 (Seminar-Project/poi-postgres-workflows): documented owner schema and archival mapping
