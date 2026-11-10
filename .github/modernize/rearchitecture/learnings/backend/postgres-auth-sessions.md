# PostgreSQL Auth Sessions and Audit-Based Throttling

Use the existing session and audit tables to migrate auth state without adding schema or writing during inspection.

## What Happened

In Seminar-Project task `mongo-postgres-auth-backend`, catalog inspection confirmed that `users.email` is the available login identifier, `auth_sessions` supports hashed refresh tokens and revocation, and `audit_logs` has JSONB/INET fields but there is no `rate_limits` table. Auth binds JWTs to `auth_sessions.id`, unions grants across the `user_roles`/`role_permissions` joins, and revokes sessions on password changes. Login failures and success resets are append-only audit events rather than destructive counter cleanup.

## Takeaway

Inspect actual columns and constraints in an explicit `READ ONLY` transaction before writing SQL. Hash refresh JWTs, use existing session revocation for logout/password changes, and use audit success markers to reset a login-failure window when no dedicated rate-limit table exists. Keep schema inspection and app-level test data isolated; do not seed roles or modify live rows as part of the migration.

## History

- 2026-11-09 (Seminar-Project/mongo-postgres-auth-backend): initial
