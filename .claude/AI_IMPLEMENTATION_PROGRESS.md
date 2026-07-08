# AI Implementation Progress

Tracks completion status against ROADMAP.md. Read this file before
starting work; update it after every completed task.

## Phase 1 — Correctness & security
- [x] 1. Fix "antropic" typo, add "anthropic" alias
- [ ] 2. Guard LLM_MODEL_ID parser against missing colon
- [ ] 3. Session ownership checks (session_id ↔ current_user)
- [ ] 4. Replace misleading admin_only decorator
- [ ] 5. Pool single MultiServerMCPClient
- [ ] 6. Fix README endpoint path mismatch
- [ ] 7. Set real SECRET_KEY via env var
- [ ] 8. Add SUPERSET_API_KEY auth path
- [ ] 9. Create ollama_model.py (local + cloud)
- [ ] 10. Uncomment data volumes, add healthchecks, fix dbt-graph-loader race

## Phase 2 — QuickSight parity features
- [ ] 11. Add "AI" top-level nav category
- [ ] 12. Build NLQ-over-semantic-layer capability
- [ ] 13. Add Q-style metadata sidecar
- [ ] 14. Add embedding/guest-token MCP tools
- [ ] 15. Add alerts/scheduled-report orchestration
- [ ] 16. Add governance/audit tools
- [ ] 17. Replace JS tool-block regex with astream_events v2
- [ ] 18. Write unit/integration tests

## Phase 3 — Advanced hardening
- [ ] 19. Migrate to in-tree mcp_service over SSE
- [ ] 20. Ollama cloud→local automatic fallback
- [ ] 21. Wire Langfuse observability
- [ ] 22. External ML anomaly detection/forecasting
- [ ] 23. Best-effort pixel-perfect PDF reporting

## BLOCKED
(none yet — log any credential/ambiguity blockers here with date and item #)
