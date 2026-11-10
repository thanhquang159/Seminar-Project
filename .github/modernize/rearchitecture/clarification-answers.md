---
schema: clarification-answers/v1
status: submitted
generated_at: "2026-11-10T09:29:48.802Z"
scope: [frontend, backend, generic]
questions_file: clarification-questions.json
---

# Rearchitecture Clarification Answers

## 🖥️ Frontend

- **F1** Which frontend framework and major version should remain the target? Please provide the exact framework and version, or confirm the current framework/version.
  - answer: Preserve current frontend framework and version (please confirm the exact name/version)
  - source: user
- **F2** Which component/UI library should the scoped map and discovery-page changes preserve? Name and major version, or confirm that no component library is in scope.
  - answer: No component library change or selection; retain existing UI patterns
  - source: user
- **F3** Provide the path or URL for the screenshot/screen recording to use as the discovery-map reference. The brief mentions a screenshot of a uniformly blue map; provide its accessible location or confirm another reference.
  - answer: http://localhost:5173/
  - source: user
- **F4** What design-system or design-token source should guide the map/discovery-page changes? Provide a source, or confirm matching the existing UI and its extracted CSS custom properties.
  - answer: Match existing UI pixel-by-pixel using extracted CSS custom properties
  - source: user
- **F5** Which accessibility standard should the scoped frontend changes target?
  - answer: WCAG 2.1 AA
  - source: user
- **F6** Which browser/runtime compatibility targets should be maintained?
  - answer: Modern evergreen browsers (Chrome, Firefox, Safari, Edge — latest 2 major versions)
  - source: user
- **F7** What responsive/breakpoint strategy should the scoped map and discovery page follow?
  - answer: Mobile-first using existing breakpoints detected from the codebase
  - source: user
- **F8** Which locales are in scope for the frontend cleanup?
  - answer: Preserve current locales and existing i18n library if present
  - source: user
- **F9** What client-side state-management preference should be followed?
  - answer: Preserve existing pattern; otherwise use minimal component state plus a server-state library
  - source: user
- **F10** What frontend routing library/strategy should be retained for this in-place cleanup?
  - answer: Match existing routes and use the de-facto router for the current framework
  - source: user

## ⚙️ Backend

- **B1** Which backend framework and major version should remain the target? Please provide the exact framework and version, or confirm the current framework/version.
  - answer: Preserve current Python backend framework and version (please confirm the exact name/version)
  - source: user
- **B2** Confirm the external API policy for routes, payloads, and status codes. The task says routes and wire contracts must stay stable; is the policy 'must preserve' for all current contracts, or only specific routes/contracts?
  - answer: must preserve
  - source: user
- **B3** Confirm the database migration strategy. The brief describes an in-place PostgreSQL migration already underway and prohibits destructive migrations/seeds against any database.
  - answer: in-place
  - source: user
- **B4** Which authentication/authorization framework and policy should be retained for the Auth domain?
  - answer: Preserve existing auth mechanism and detect it from the codebase
  - source: user
- **B5** What latency, throughput, and availability targets should the cleaned-up runtime meet?
  - answer: Match current production baseline; no regression
  - source: user

## 📋 General

- **G1** Confirm the definition of success. The brief requires all required product behavior and stable routes/wire contracts, with the specified Python, Ruff, and frontend validation completed.
  - answer: Preserve all required product behavior and API contracts; requested validations pass
  - source: user
- **G2** Confirm the explicit boundaries: no destructive live-database migrations/seeds, no deletion/reversion of user data or existing edits, no rebuilding PMTiles from empty placeholders, and no unrelated style/security work. Anything else out of scope?
  - answer: Use the stated boundaries; infer other exclusions from repository structure
  - source: user
- **G3** Confirm the test policy. The brief calls for targeted Python PostgreSQL tests, Ruff, and frontend lint/tests/build, while preserving or rewriting useful regression coverage rather than deleting tests blindly.
  - answer: partial: targeted Python PostgreSQL tests, Ruff, frontend lint/tests/build; preserve or rewrite useful regression coverage
  - source: user
- **G5** Add or confirm any additional requirements, exclusions, dependencies, compliance rules, or operational constraints not already captured above.
  - answer: None beyond the decisions listed in this specification.
  - source: user
