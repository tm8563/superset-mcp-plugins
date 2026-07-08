# ROADMAP — superset-mcp-plugins

The itemized implementation spec. The AI agent works these in order, one per
loop fire, per the rules in `CLAUDE.md`. Status checkboxes live in
`.claude/AI_IMPLEMENTATION_PROGRESS.md`.

## Phase 1 — Correctness & security

1. **Fix "antropic" typo, add "anthropic" alias.** In
   `superset_chat/app/models/__init__.py` the provider dispatch matches only
   the misspelled `antropic`, so the canonical `anthropic:...` silently falls
   back to `MockChatModel`. Accept `anthropic` (canonical) and `antropic`
   (backward-compatible alias). Rename `inference/antropic_model.py` →
   `anthropic_model.py` and fix its stale `ChatBedrock` docstrings.
   *Acceptance: `LLM_MODEL_ID=anthropic:...` and `antropic:...` both select
   `ChatAnthropic`; unknown providers still fall back to `MockChatModel`.*

2. **Guard `LLM_MODEL_ID` parser against missing colon.**
   `superset_chat/app/models/__init__.py:5` does
   `os.environ.get('LLM_MODEL_ID','mock:mock').split(':', 1)` — a value with
   no `:` raises `ValueError` at import time, crashing the plugin. Wrap the
   parse in a try/except, default to `('mock','mock')` on failure, and log a
   clear warning. Also warn loudly (not silently) whenever the dispatch falls
   back to `MockChatModel`.
   *Acceptance: `LLM_MODEL_ID=garbage` (no colon) no longer raises; plugin
   imports; a warning is logged; `MockChatModel` fallback is logged.*

3. **Session ownership checks (session_id ↔ current_user).** The chat
   endpoints in `superset_chat/ai_superset_assistant.py` accept an arbitrary
   `session_id` from the POST body with no ownership check; the shared
   Postgres checkpointer is keyed only by `thread_id`, allowing cross-user
   conversation hijacking. Bind each session to `current_user.username` at
   creation and reject mismatches on `chat`/`chat_stream`/`clear_session`.
   *Acceptance: a user cannot read/append to another user's session_id.*

4. **Replace misleading `admin_only` decorator.** `admin_only` in
   `ai_superset_assistant.py` only checks `current_user.is_authenticated`,
   giving every logged-in user the assistant. Either enforce a real admin
   role check or rename it to `login_required` to reflect actual behavior.
   Prefer a configurable role allowlist (env `AI_ASSISTANT_ALLOWED_ROLES`).
   *Acceptance: decorator name matches behavior, or role check is enforced.*

5. **Pool a single `MultiServerMCPClient`.** `superset_chat/app/server/llm.py`
   spawns the stdio MCP client fresh on every chat message (high latency,
   resource leak). Build/reuse one client + subprocess per `LLMAgent` (or
   app-lifetime singleton) and reuse across requests; tear down on shutdown.
   *Acceptance: second+ chat message does not respawn the MCP subprocess;
   latency drops; no leaked processes.*

6. **Fix README endpoint path mismatch.** `README.md` documents
   `/ai_superset_assistant/api/...` but the Flask-AppBuilder route prefix is
   `/aisupersetassistantview/api/...` (auto-derived from the class name), so
   the documented curl examples 404. Correct the README (or alias both).
   *Acceptance: README curl examples hit a real endpoint.*

7. **Set real `SECRET_KEY` via env var.** `superset/superset_config.py` ships
   a literal placeholder `SECRET_KEY`. Read from `SUPERSET_SECRET_KEY` env
   (fail loudly if unset in non-dev mode) with a safe dev fallback.
   *Acceptance: no hardcoded secret in the config; production start fails
   fast if unset.*

8. **Add `SUPERSET_API_KEY` auth path.** The agent reaches Superset via a
   service-account username/password (`SUPERSET_USERNAME`/`SUPERSET_PASSWORD`),
   bypassing per-user RBAC. Add an API-key path: pass `SUPERSET_API_KEY` to
   the MCP server so it uses `Authorization: Bearer <key>` against a
   `FAB_API_KEY_ENABLED` Superset. Prefer the key over username/password when
   both are set.
   *Acceptance: with `SUPERSET_API_KEY` set, the MCP server authenticates via
   the API key, not the service-account login.*

9. **Create `ollama_model.py` (local + cloud).** Add an `ollama` provider
   branch to `models/__init__.py` and a new
   `superset_chat/app/models/inference/ollama_model.py` subclassing
   `langchain_ollama.ChatOllama`. LOCAL: `OLLAMA_BASE_URL=http://localhost:11434`,
   no auth. CLOUD: `OLLAMA_BASE_URL=https://ollama.com` + `OLLAMA_API_KEY`
   sent as `Authorization: Bearer` via `client_kwargs['headers']`. Add
   `langchain-ollama` to `pyproject.toml`. Document in `template.env` +
   `README.md`. `temperature=0`.
   *Acceptance: `LLM_MODEL_ID=ollama:llama3.1` loads the Ollama backend; cloud
   mode sends the bearer header; unknown/missing key degrades gracefully.*

10. **Uncomment data volumes, add healthchecks, fix dbt-graph-loader race.**
    In `docker-compose.yaml`: uncomment the postgres/falkordb volume mounts
    (so `docker compose down` doesn't wipe data); add healthchecks for
    `superset`, `falkordb`, `educational-dbt-docs`; make `dbt-graph-loader`
    depend on `educational-dbt-docs` producing `target/manifest.json` (fix the
    race).
    *Acceptance: `docker compose down && up` preserves state; healthchecks
    present; graph-loader runs after the manifest exists.*

## Phase 2 — QuickSight parity features

11. **Add "AI" top-level nav category.** Register the assistant view under a
    dedicated top-level `AI` category instead of burying it in "Custom Tools".
12. **Build NLQ-over-semantic-layer capability.** ReAct agent + a
    `semantic_layer` MCP tool surface reading `superset/semantic_layers/` +
    dataset/column/metric `description` fields; produce SQL via structured
    output, run via `sql_lab/execute/`.
13. **Add Q-style metadata sidecar.** Synonyms, friendly names, primary date
    field, default/disallowed aggregations stored alongside datasets.
14. **Add embedding/guest-token MCP tools.** `configure_embedding`,
    `get_embedding`, `mint_guest_token`, `build_embed_url`,
    `revoke_guest_tokens`. Runner needs `can_grant_guest_token`; never log
    raw tokens (sha256 audit only).
15. **Add alerts/scheduled-report orchestration.** Wrap `/api/v1/report/`
    endpoints; add an on-demand snapshot trigger tool.
16. **Add governance/audit tools.** `list_rls`, `list_roles`, `list_tags`.
17. **Replace JS tool-block regex with `astream_events` v2.** Drop the brittle
    `Start Running Tool:`/`Tool Output:` regex parsing in
    `templates/ai_assistant.html`; consume structured events.
18. **Write unit/integration tests.** Cover the model dispatch + streaming
    endpoint.

## Phase 3 — Advanced hardening

19. **Migrate to in-tree `mcp_service` over SSE.** Point the plugin at
    Superset's built-in `superset/mcp_service` (RBAC-enforced, fail-closed)
    instead of the alpha `superset-mcp-server`.
20. **Ollama cloud→local automatic fallback.** On connection failure against
    `OLLAMA_BASE_URL`, retry then switch to `OLLAMA_FALLBACK_BASE_URL`.
21. **Wire Langfuse observability.** Into the Ollama path too.
22. **External ML anomaly detection/forecasting.** MCP tool calling
    Prophet/SageMaker/RCF over Superset datasets; LLM writes autonarratives.
23. **Best-effort pixel-perfect PDF reporting.** Headless PDF renderer over
    Superset data; document the gap vs QuickSight paginated reports.