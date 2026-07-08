# AI Implementation Progress

Checkbox tracker for `.claude/ROADMAP.md`. The spec lives in
`CLAUDE.md` (rules) and `.claude/ROADMAP.md` (items) — this file only
records completion status. Read ROADMAP.md for what each numbered item is.

## Closing summary — ALL FOUR PHASES COMPLETE (2026-07-08)

All 29 roadmap items are implemented, verified, committed, and pushed to
`origin/roadmap/phase1-correctness` (HEAD `7a6b32b`). The full test suite
passes (154 tests; stdlib `unittest`, run with `python3 -m unittest discover
-s tests`). Git is clean and in sync with origin (0 ahead / 0 behind). No
items are blocked (`## BLOCKED` is empty).

- **Phase 1 — Correctness & security: 10/10** (#1–#10) — antropic typo/alias;
  safe `LLM_MODEL_ID` parsing + audible fallback warnings; session-ownership
  + namespaced checkpointer thread_id; role-checked access; pooled
  `MultiServerMCPClient`; correct README routes; env-driven `SECRET_KEY`
  (prod fail-fast); `SUPERSET_API_KEY` auth path; Ollama local+cloud;
  persistent volumes + healthchecks + dbt-graph-loader race fix.
- **Phase 2 — QuickSight parity features: 8/8** (#11–#18) — "AI" nav
  category; NLQ over the semantic layer; Q-style metadata sidecar in dataset
  `extra`; embedding/guest-token MCP tools (sha256-audit); alerts/scheduled-
  report orchestration + on-demand trigger; governance/audit tools
  (list_rls/list_roles/list_tags); structured `astream_events` v2 streaming
  (JS regex replaced); unit/integration test suite.
- **Phase 3 — Advanced hardening: 5/5** (#19–#23) — in-tree `mcp_service`
  over streamable-http (stdio preserved as default); Ollama cloud→local
  automatic fallback; robust Langfuse wiring (covers the Ollama path);
  ML anomaly-detection + forecasting tools; best-effort PDF/screenshot
  reporting via Superset's existing machinery (gap vs QuickSight documented).
- **Phase 4 — User-friendly UX: 6/6** (#24–#29) — zero-setup capability
  disclosure (derived from the real tool surface; replaced stale Airflow
  welcome); context-aware dataset-grounded prompt suggestions (replaced stale
  showExamples); plain-language categorized error recovery (no stack traces);
  one-line tool-use summaries with raw payload behind expand; minimal-friction
  onboarding smoke test (no topic/dataset training step) + README note; early
  'thinking' streaming indicator so the UI never feels frozen.

Config reconciliation with the real `/home/mlfts/superset` instance + the #19
mcp_service investigation are logged below. Real-instance validation was
performed throughout (live REST probes: `/health`, login, datasets, reports,
RLS/roles/tags, the mcp_service streamable-http endpoint, screenshot
endpoints) — no secrets committed (real creds live in the gitignored
plugin-root `.env`).

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
- [x] 15
- [x] 16
- [x] 17
- [x] 18

## Phase 3 — Advanced hardening
- [x] 19
- [x] 20
- [x] 21
- [x] 22
- [x] 23

## Phase 4 — User-friendly UX
- [x] 24
- [x] 25
- [x] 26
- [x] 27
- [x] 28
- [x] 29

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

## #19 investigation — in-tree mcp_service over streamable-http (2026-07-08)

Per the #19 guardrails, confirmed whether `/home/mlfts/superset`'s in-tree
mcp_service can be started and reached — WITHOUT modifying the Superset
checkout (only `docker exec` into the existing `superset-superset-1` container).

Findings (validated live):
- The `superset mcp` CLI exists in the live container (`/app/.venv/bin/superset`).
  `superset mcp run --host 0.0.0.0 --port 5008` starts the service; it registers
  ~70 RBAC-protected tools.
- **Transport: streamable-http (stateless) at `/mcp`** — confirmed in the boot
  log ("Starting MCP server ... with transport 'streamable-http' (stateless) on
  http://0.0.0.0:5008/mcp"). `GET /mcp` -> 405 (POST-only MCP protocol);
  `/sse` -> 404 (no legacy SSE endpoint). Uvicorn on 0.0.0.0:5008.
- Auth: JWT (FastMCP BearerAuthProvider) / API-key passthrough (needs
  `FAB_API_KEY_ENABLED`, which is OFF on the real instance) / `MCP_DEV_USERNAME`
  dev fallback (unset on the real instance). The endpoint is reachable without
  a token (405 on GET); actual tool calls require a Bearer token
  (`SUPERSET_API_KEY` after enabling FAB_API_KEY_ENABLED, or an MCP service JWT
  in `MCP_TOKEN`).
- **No checkout modification needed** → NOT blocked. The plugin-side integration
  is additive: `TRANSPORT_TYPE=streamable_http` selects `http://{mcp_host}/mcp`
  with `transport=streamable_http` and `Authorization: Bearer <SUPERSET_API_KEY
  | MCP_TOKEN>`; `stdio` remains the default (unchanged), so the plugin works
  exactly as before if streamable-http isn't set up. The legacy `sse` branch
  (`/sse`) is kept for other SSE MCP servers but the in-tree mcp_service does
  not serve it.
- Caveat: the plugin's own `docker-compose.yaml` `mcp_service` service builds
  from `apache/superset:4.1.1`, which may NOT ship the `superset mcp` CLI; the
  real `/home/mlfts/superset` build does. Against the real instance, run
  `superset mcp run` in the superset container (or point a service at the real
  image).

Verified: 11 behavioral checks (streamable_http -> /mcp + Bearer; SUPERSET_API_KEY
preferred over MCP_TOKEN; MCP_SERVICE_URL override; sse -> /sse; stdio default +
env intact; no-token -> empty headers); full suite 85 tests pass; `docker compose
config` valid. Live reachability confirmed via `docker exec` probe.

## #23 investigation — best-effort PDF reporting (2026-07-08)

Investigated Superset's EXISTING screenshot/PDF machinery in
/home/mlfts/superset before building anything (per the #23 guidance):
- REST: `POST /api/v1/dashboard/<id>/cache_dashboard_screenshot/` (trigger),
  `GET /api/v1/dashboard/<id>/screenshot/<digest>/` (PNG fetch), and the
  chart equivalents `GET /api/v1/chart/<id>/cache_screenshot/` +
  `GET /api/v1/chart/<id>/screenshot/<digest>/` (confirmed in the openapi +
  dashboards/api.py + charts/api.py). `digest = get_dashboard_digest(dashboard)`.
- Server-side PDF: `superset/utils/pdf.py:build_pdf_from_screenshots` builds
  paginated PDFs inside the reports worker (delivered via email/Slack, NOT a
  downloadable REST endpoint); reached via the #15 `ExecuteReport` tool.
- Celery worker: `superset/tasks/thumbnails.py` (`cache_dashboard_screenshot`,
  `cache_chart_thumbnail`) via Playwright. charts/api.py gates screenshot
  endpoints behind `ensure_thumbnails_enabled`.
- Live instance: `ENABLE_PLAYWRIGHT=false` -> the screenshot endpoints return
  404 (confirmed: `POST .../cache_dashboard_screenshot/` -> 404,
  `GET .../screenshot/digest/` -> 404). So no screenshot can be produced on
  the real dev instance until Playwright is enabled.

Implementation (wraps the existing machinery, no new renderer):
- `pdf_reports.py`: `trigger_dashboard_screenshot` / `get_dashboard_screenshot`
  / `trigger_chart_screenshot` / `get_chart_screenshot` (raw PNG bytes via a
  new `SupersetRestClient.get_bytes`), `screenshot_to_pdf` (BEST-EFFORT
  single-page PNG->PDF via reportlab if installed, else None), and
  `export_dashboard_pdf` (fetch + best-effort PDF, PNG fallback, writes a file
  + returns a gap note). `PdfReportTools` (TriggerDashboardScreenshot,
  TriggerChartScreenshot, ExportDashboardPdf) wired into the ReAct agent.

GAP vs QuickSight paginated reports (documented honestly, not overclaimed):
- No pixel-perfect multi-page layout control (header/footer, page breaks,
  repeating table headers). Client-side path is a single image-in-PDF.
- No bursting (per-recipient segmented output).
- No scheduled batch PDF generation from the plugin; Superset's scheduled
  reports + `build_pdf_from_screenshots` are the server-side equivalent
  (reached via #15 ExecuteReport), not a new renderer here.
- Requires Superset's Playwright worker enabled to produce any output; else
  the screenshot endpoints 404.

Verified: 12 behavioral checks (trigger/fetch paths incl. trailing slash;
get_bytes PNG; best-effort PDF None on no-reportlab/invalid; PNG fallback +
gap note; tool wrappers); integration — the agent's tools include the 3 PDF
tools. Added tests/test_pdf_reports.py (8 tests); full suite 118 tests pass.
Live: endpoint paths confirmed in the openapi + source; the live dev instance
404s because Playwright is off (documented, not a plugin bug).

## BLOCKED
(none yet — log any credential/ambiguity blockers here with date and item #)

### 2026-07-08 — installing the plugin into the real /home/mlfts/superset instance (deployment verification, not a roadmap item)

BLOCKED by a dependency-version conflict: the plugin targets
`apache/superset:4.1.1` (marshmallow 3 / starlette 0.x / packaging 24), but the
real `/home/mlfts/superset` dev instance is a newer build (marshmallow 4.3.0 /
starlette 1.3.1 / packaging 25.0). A `pip install -e` of the plugin (the README
install path) would DOWNGRADE Superset-critical packages and break the instance
(confirmed via `pip install --dry-run`):

- `marshmallow` 4.3.0 -> 3.26.2 (pinned `<4` by `langchain-community==0.3`) —
  breaks FAB/Superset schemas.
- `starlette` 1.3.1 -> 0.37.2 (pinned `<0.38` by `superset-mcp-server==0.1.0a5`)
  — breaks the ASGI stack.
- `packaging` 25.0 -> 24.2 (pinned `<25` by `langchain-core`).

NOT performed — the breaking install was aborted; the instance was left
untouched (copied plugin dir removed, `/health` OK, package versions
unchanged). No `FLASK_APP_MUTATOR` was added and no `pip install` was run.

Paths forward (need user decision):
1. Run the plugin against its OWN docker-compose stack
   (`apache/superset:4.1.1`, the repo's `docker-compose.yaml` Quick Start),
   which has the older compatible deps — the user can click through the AI
   Assistant there.
2. Upgrade the plugin's deps to marshmallow-4 / starlette-1-compatible versions
  (newer `langchain-community`/`superset-mcp-server`, or drop the alpha
  `superset-mcp-server` in favor of the in-tree `mcp_service` from #19) and
  re-pin — a separate compatibility effort.
3. Point the plugin at a Superset 4.1.1 instance (matches its pinned deps).

UX roadmap items #24–#29 remain COMPLETE (code + tests); this blocker only
affects installing into THIS specific newer real instance.