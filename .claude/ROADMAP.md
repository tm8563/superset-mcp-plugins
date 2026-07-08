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

## Phase 4 — User-friendly UX (avoiding QuickSight Q's known UX failures)

QuickSight Q's biggest complaints were (a) forcing topic/synonym curation
before first use, (b) a blank input box with no grounding, and (c) opaque
errors. This phase makes the assistant usable on first open with zero manual
curation, surfaces what it can do, and keeps tool-use visible without clutter.
The current template (`superset_chat/templates/ai_assistant.html`) still ships
stale Airflow-DAG copy in `newChat()`'s welcome and `showExamples()` — wrong
domain — so several items also fix that regression.

24. **Zero-setup capability disclosure.** On first open (and via a persistent
    "What can I ask?" affordance), show the user what this assistant can
    actually do — NLQ over datasets, list/summarize dashboards, alerts &
    scheduled reports, governance (RLS/roles/tags), embedding/guest tokens,
    PDF/screenshot export, ML anomaly/forecast — WITHOUT requiring any manual
    topic/synonym setup. The capability list is derived from the agent's actual
    tool surface (the `*Tools` lists wired in `llm.py`), not a hardcoded
    string. The `#13` Q-style sidecar already auto-populates per-dataset
    metadata; surface it, never gate the assistant behind a curation step.
    Replace the stale `newChat()` welcome (Airflow DAGs) with this real
    capability list.
    *Acceptance: a fresh user sees the real capability set on first open with
    no setup step; the welcome is Superset-relevant, not Airflow; a persistent
    affordance re-shows it.*

25. **Context-aware prompt suggestions.** When the user opens the assistant
    with a dataset context (a dataset picker in the UI, or a `?dataset_id=`
    query param on the view URL), suggest 3-4 example questions grounded in
    that dataset's actual columns/metrics — generated from
    `semantic_layer.get_semantic_layer_context` (columns, metrics, sidecar
    synonyms/friendly name) — instead of a blank input box. Replace the stale
    hardcoded `showExamples()` (Airflow DAGs) with these. Provide a small
    "suggested questions" row above the input that populates the box on click.
    *Acceptance: with a dataset selected, the UI shows 3-4 dataset-grounded
    suggestions using real columns/metrics; clicking one fills the input;
    no suggestion references Airflow/DAGs.*

26. **Plain-language error recovery.** Audit every place the chat can fail —
    LLM unreachable (incl. Ollama fallback exhausted), MCP tool error,
    malformed/failed SQL, auth/permission failure, Superset REST error — and
    ensure the user sees a clear, non-technical explanation + a suggested next
    step, never a stack trace or raw exception string. Categorize errors at the
    source (`llm.py` `get_response_stream` error yield, the tool wrappers'
    exceptions) into a structured `{'type':'error','category','message','
    next_step'}` event on the #17 streaming path; the template renders the
    category + message + next step. Build on the existing `case 'error'`
    handler and `addMessage('Sorry, I encountered an error...')` fallback.
    *Acceptance: each failure mode produces a categorized, user-friendly
    message + next step; no raw exception/stack trace reaches the UI; cover
    LLM-down, MCP-tool-error, SQL-failure, auth-failure.*

27. **Visible tool-use transparency without clutter.** When the agent runs a
    tool (NLQ→SQL, screenshot trigger, report execution, governance read),
    show a lightweight, collapsible "thinking" indicator — tool name + a
    one-line summary — rather than a wall of raw JSON. The #17 `createToolBlock`
    already collapses by default but renders full input/output `pre` blocks;
    add a one-line human summary (e.g. "Listing dashboards…" / "Running SQL
    on dataset 5…") and truncate/hide the raw payload behind the expand
    toggle. Reduces cognitive load (Hick's Law) while keeping trust.
    *Acceptance: each running tool shows a one-line summary + collapsible
    detail; the collapsed view never shows a wall of raw JSON; expand still
    reveals the full payload.*

28. **Minimal-friction onboarding.** Verify end-to-end that a fresh user can
    ask a real natural-language question against a real dataset with zero
    prior configuration beyond what `#13`'s sidecar already auto-populates —
    no separate "topic" or "dataset training" step. Add a smoke test (and a
    README note) that demonstrates the path: open assistant → pick a dataset
    → ask a question → get a grounded answer, with no manual curation.
    *Acceptance: a smoke test passes (and is documented) showing a real
    question answered against a real dataset with only the auto-populated
    sidecar; no training/curation step is required or mentioned.*

29. **Response streaming feel.** Verify perceived latency — the first token
    or a tool-start "thinking" indicator should appear within ~1s of sending
    a message, even if the full answer takes longer, so the UI never feels
    frozen. The `#5` MCP pool already removes per-message subprocess respawn;
    ensure the streaming path emits an early indicator (emit a `thinking`
    event, or rely on the first `tool_start`/`chunk`) immediately on message
    receipt, and that the template shows the typing indicator right away
    (it already toggles `typingIndicator` before the fetch). Add a guard/test
    that an early event is emitted before the first LLM token.
    *Acceptance: an early indicator (typing/thinking or first token) is shown
    within ~1s of send; the UI does not appear frozen during a slow answer;
    verified by a test asserting an early event is emitted before the first
    chunk.*