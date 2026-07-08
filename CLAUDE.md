# CLAUDE.md — project rules for superset-mcp-plugins

Rules the AI agent MUST follow when implementing roadmap items. Read this
file before starting any item. The itemized spec lives in
`.claude/ROADMAP.md`; `.claude/AI_IMPLEMENTATION_PROGRESS.md` is a
checkbox tracker only.

## Repository

- **Project:** `superset-mcp-plugins` (pip package `superset-chat`) — an
  Apache Superset Flask-AppBuilder plugin embedding a LangGraph/LangChain
  ReAct agent that talks to Superset via MCP. See `README.md` for the
  full architecture.
- **Stack:** Python (Poetry-managed), Flask / Flask-AppBuilder,
  LangChain / LangGraph, `langchain-mcp-adapters`, PostgreSQL checkpointer,
  optional FalkorDB/Neo4j for dbt lineage.
- **Remote:** `origin` → `https://github.com/tm8563/superset-mcp-plugins.git`
- **Working branch:** `roadmap/phase1-correctness` (current phase).

## Loop workflow (one item per fire)

1. **Sync & verify clean.** `git fetch origin --prune`; confirm the working
   branch is in sync with `origin/<branch>` and `git status` is clean before
   starting. If local and origin diverge, pull first.
2. **Pick the next unfinished item** from `.claude/ROADMAP.md`, cross-checked
   against the checkboxes in `.claude/AI_IMPLEMENTATION_PROGRESS.md`. Take
   items in order (lowest number first) unless an earlier item is blocked.
3. **Implement end-to-end.** Make the change scoped to that single item — do
   not bundle unrelated edits into the same commit.
4. **Verify before committing.** Do NOT commit on syntax alone. Exercise the
   changed code path: `python3 -c "import ast; ast.parse(...)"` for syntax,
   then a behavioral check that actually runs the changed logic (stub heavy
   deps like `langchain_core` / `langchain_anthropic` if they aren't
   installed locally — see the item-#1 commit for the pattern). Confirm the
   fix works AND that existing fallback/alias behavior still works.
5. **Update the checkbox** for that item to `[x]` in
   `.claude/AI_IMPLEMENTATION_PROGRESS.md`, in the same commit as the change.
6. **Commit, then push immediately.** Never leave a commit local-only between
   loop fires. `git commit` then `git push origin <branch>`.
7. **If blocked** (missing credentials, ambiguity, upstream failure), log it
   under `## BLOCKED` in the progress file with the date and item #, and stop
   — do not commit a half-finished item.

## Commit conventions

- Prefix: `FEAT:` / `FIX:` / `DOCS:` / `REFACTOR:` / `TEST:` followed by a
  short imperative summary, then `(roadmap #N)` referencing the item.
- Body: what changed and why; note verification performed.
- Always end the message with:
  `Co-Authored-By: Claude <noreply@anthropic.com>`
- Keep commits atomic — one roadmap item per commit (doc/setup commits like
  creating CLAUDE.md/ROADMAP.md are the exception).

## Code conventions

- Match the surrounding style: single quotes for strings, `temperature=0`
  for LLM wrappers, provider dispatch pattern in
  `superset_chat/app/models/__init__.py`.
- Preserve backward compatibility when the roadmap says "alias" or "fallback"
  — never remove a working entrypoint to fix a typo.
- Don't introduce new dependencies mid-item unless the roadmap item requires
  it; if it does, add to `pyproject.toml` and note it in the commit.
- No `print` debugging left in committed code; no leftover `console.log` in
  templates.

## Spec vs. status

- `.claude/ROADMAP.md` = the spec (what each item is, which file(s), the
  acceptance criterion). Edit it only to refine an item's spec.
- `.claude/AI_IMPLEMENTATION_PROGRESS.md` = checkboxes + blocked log only.
  Do not put the spec text there.