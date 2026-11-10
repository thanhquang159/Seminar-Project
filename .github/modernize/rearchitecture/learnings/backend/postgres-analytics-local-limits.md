# PostgreSQL Analytics and Local Limits

Analytics routes should use the existing PostgreSQL session/schema directly and avoid introducing Redis when the current deployment can accept process-local presence and rate-limit state.

## What Happened

For `Seminar-Project/analytics-postgres-backend`, schema inspection found no analytics session/read-model tables and no persistent rate-limit table. PostgreSQL analytics events have a consent FK, JSONB properties, and no session identifier. Runtime hourly counters have a unique bucket/name/dimensions key; AI daily quotas have a unique user/date key. The route migration used event-time queries, advisory locking for consent writes, atomic quota upserts, and bounded in-memory presence/rate limits.

## Takeaway

Use the application's `AsyncSession` and existing constraints; do not create indexes/tables from request paths. Report metrics that cannot be derived from the schema as unavailable instead of substituting zero. Process-local limits avoid a new Redis dependency, but document that they reset on restart and do not coordinate across workers.

## History

- 2026-11-09 (Seminar-Project/analytics-postgres-backend): initial
