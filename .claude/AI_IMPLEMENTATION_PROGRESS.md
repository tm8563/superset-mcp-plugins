# AI Implementation Progress

Checkbox tracker for `.claude/ROADMAP.md`. The spec lives in
`CLAUDE.md` (rules) and `.claude/ROADMAP.md` (items) — this file only
records completion status. Read ROADMAP.md for what each numbered item is.

## Phase 1 — Correctness & security
- [x] 1
- [x] 2
- [x] 3
- [x] 4
- [x] 5
- [x] 6
- [x] 7
- [x] 8
- [x] 9
- [x] 10

## Phase 2 — QuickSight parity features
- [x] 11
- [x] 12
- [x] 13
- [x] 14
- [ ] 15
- [ ] 16
- [ ] 17
- [ ] 18

## Phase 3 — Advanced hardening
- [ ] 19
- [ ] 20
- [ ] 21
- [ ] 22
- [ ] 23

## Config reconciliation (2026-07-08)

Reconciled the plugin's config against the real `/home/mlfts/superset` dev
instance — read its `docker-compose.yml` + `docker/.env` +
`docker/docker-init.sh`, and validated against the live stack (`superset-superset-1`
on :8088, `superset-db-1` on 127.0.0.1:5432): `/health` OK; `admin`/`admin`
login returns a JWT; `GET /api/v1/dataset/` returns count=21; a bearer API key
is rejected (HTTP 422) → `FAB_API_KEY_ENABLED` is off.

Mismatches found & fixed (infrastructure alignment, not a roadmap task):
- **SUPERSET_USERNAME/PASSWORD:** plugin assumed `superset_admin`/`superset`
  (its own demo stack); real instance uses `admin`/`admin` (docker-init.sh
  default). Real values written to the gitignored plugin-root `.env`;
  `template.env` documents the mismatch without committing secrets.
- **SQLALCHEMY_DATABASE_URI:** plugin assumed
  `postgres:postgres@postgres:5432/postgres` (own stack); real instance is
  `superset:superset@db:5432/superset` (host: `localhost:5432`). Real value in
  gitignored `.env`; `template.env` notes the real-instance URI.
- **FAB_API_KEY_ENABLED off:** the #8 API-key path is unavailable on the real
  instance; username/password (JWT) is the working auth path. `.env` +
  `template.env` reflect this (no `SUPERSET_API_KEY` set).
- **In-tree mcp_service not exposed:** SSE/`MCP_TOKEN` unavailable; stdio is
  the working transport. Added `TRANSPORT_TYPE=stdio` to `template.env` + `.env`.
- **SUPERSET_API_URL:** already `http://localhost:8088` (matches real port
  8088); kept.

Files: created gitignored `.env` (real values, NOT committed); updated
`template.env` (documentation only, no secrets). No real secrets committed
(verified `.env` is gitignored; `superset/superset.env` is tracked and was
left alone).

## BLOCKED
(none yet — log any credential/ambiguity blockers here with date and item #)