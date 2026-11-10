# PostgreSQL Audio Task Services

Use the existing UUID/FK-constrained audio and localization tables with short-lived async sessions for background work.

## What Happened

During `Seminar-Project/mongo-postgres-audio`, read-only schema inspection showed `audio_tasks.localization_id` is non-null and references `poi_localizations`, while the task manager runs beyond the request lifetime. The worker therefore uses `AsyncSessionLocal` per operation and only enqueues tasks for persisted localization rows. The existing schema has no `rate_limits`, `meta`, or deletion-tombstone table.

## Takeaway

Do not retain a request-scoped `AsyncSession` in a singleton task manager. Store the app session factory, translate API statuses at the service boundary, and persist request limits in the existing localization log's JSONB metadata when no dedicated rate table exists. Derive sync cursors from POI timestamps only as an explicit fallback; never claim deletion parity without a tombstone source.

## History

- 2026-11-09 (`Seminar-Project/mongo-postgres-audio`): initial
