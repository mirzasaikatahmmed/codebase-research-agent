# DECISIONS.md

## Architecture Overview

The system is a Django REST API that wraps an AI agent. When `POST /api/sessions/` is called:

1. The server gets or creates a `Repository` record for the given URL
2. Creates a `ResearchSession` with status `pending`
3. Clones the repo via `git clone --depth 1` (cached in `~/.cache/codefusion_repos/`)
4. Runs the agent loop — Claude receives a system prompt and 7 tools, calls them in sequence, and the server executes each call and feeds results back
5. The loop continues until `stop_reason == "end_turn"` (Claude is done) or the 25-iteration cap is hit
6. The final answer, token usage, and status are persisted; the full session is returned

The agent loop is in `agent/core/agent.py`. Tools are split into two groups: code exploration (`agent/tools/code_explorer.py`) and database interaction (`agent/tools/db_tools.py`). This separation keeps each file focused and makes it easy to add new tools to either category.

---

## Database Schema Rationale

Four models, each with a clear purpose:

**`Repository`** — deduplicated record per GitHub URL. The `url` field is the natural key (unique). `last_analyzed` lets callers see freshness without querying sessions. At scale, add a `clone_status` field and move cloning to a background job.

**`ResearchSession`** — one row per question asked. Tracks the full lifecycle (`pending → running → complete/failed`), token usage, the final answer, error messages, and timestamps. Storing token counts on the session (not just in tool logs) enables cost reporting without expensive aggregation queries.

**`Finding`** — what the agent deliberately decided was worth remembering. Distinct from tool call logs: a finding is a "this matters" signal written by the agent calling `save_finding()`. The `line_start`/`line_end` fields make findings directly navigable in source. Findings from session A are visible to sessions B and C on the same repo — this is the core DB→agent feedback loop that prevents re-exploring the same code repeatedly.

**`ToolCallLog`** — complete audit trail of every tool call with full input/output JSON. Used for debugging, cost analysis, and demonstrating multi-step reasoning. Kept separate from `Finding` so findings stay high-signal and logs stay comprehensive.

**Trade-offs considered:**
- Token counts accumulated as running totals on `ResearchSession` — a failed mid-session still has partial token data for cost investigation.
- `Finding` stores only the agent's note, not the raw file content — keeps the DB small. At scale, store a content snippet for faster retrieval.
- No `Message` model for full conversation history — storing multi-turn context would bloat the DB significantly for minimal benefit given the tool call log already shows the full reasoning trail.

**At scale:** Add indexes on `ResearchSession.status`, `Finding.session_id`, and `Finding.file_path`. Move agent execution to a Celery task so the API returns `202 Accepted` immediately and the client polls for completion.

---

## Key Design Decisions and Trade-offs

**Synchronous execution in the request cycle**
Simple and correct for this scope. The downside is request timeout risk on large repos or complex questions. The fix (Celery + polling endpoint) is well-understood but adds 3+ infrastructure components. Synchronous is the right call here.

**`git clone --depth 1` with a persistent cache**
Shallow clone is dramatically faster (FastAPI: ~2s vs ~30s for full history). Repos are cached in `~/.cache/codefusion_repos/` and reused across sessions — repeat questions skip cloning entirely and only `git pull --ff-only`. The cache grows unboundedly; in production, add TTL-based eviction.

**Tool output capped at 8 KB**
Without this, a `read_file` on a 5,000-line module floods the context window and pushes earlier reasoning out. The cap forces the agent to be selective (use `start_line`/`end_line`), which is the correct behavior anyway.

**25-iteration cap**
Prevents infinite loops. Simple questions resolve in 5–8 iterations; complex ones in 12–18. 25 gives headroom without runaway cost.

**`match` statement for tool dispatch**
Python 3.10+ only. Clean and explicit — adding a new tool is one `case` clause. A dict of callables would add indirection for no benefit at this scale.

**`CsrfExemptSessionAuthentication`**
DRF's default `SessionAuthentication` enforces CSRF on every non-GET request, which breaks curl, Postman, and Swagger UI flows (all of which don't send `X-CSRFToken`). Since this is a pure REST API with no browser form submissions, CSRF enforcement provides no security benefit. The custom subclass overrides `enforce_csrf()` to skip it, while keeping session-based identity intact. The Django admin is unaffected — it uses Django's own CSRF middleware independently.

**Login endpoint accepts username or email**
Users naturally try their email. The login view tries `authenticate(username=identifier)` first; if that fails it looks up the user by email and retries. This adds one extra DB query on email login — acceptable at this scale and avoids a confusing UX.

**Jazzmin admin theme**
The default Django admin is functional but visually dated. Jazzmin replaces it with a Bootstrap 5 dark sidebar theme with per-model icons, inline displays, and top navbar links to the API docs. Zero custom HTML or CSS required — all configured via `JAZZMIN_SETTINGS` in `settings.py`.

**`drf-spectacular` for OpenAPI/Swagger**
Auto-generates the schema from DRF views and serializers. `@extend_schema` decorators add summaries, descriptions, and tag groupings (`Auth`, `Sessions`, `Repositories`). `cookieAuth (apiKey)` is auto-detected from `SessionAuthentication`. `withCredentials: true` in `SWAGGER_UI_SETTINGS` ensures the browser sends the session cookie on Swagger requests after login.

---

## What I'd Do Differently with More Time

- **Async execution**: Move agent runs to Celery. Return `202 Accepted` with the session ID, add `GET /api/sessions/:id/status` for polling, and show streaming tool call progress via SSE.
- **Smarter context management**: Track total message history tokens and summarize older turns when approaching the model's context limit, rather than relying solely on per-tool output truncation.
- **Semantic search**: Index repo files with embeddings on first clone. `search_code` hits vector search first for concept-level queries before falling back to string matching.
- **Rate limiting + cost budgets**: Per-repo or per-user token budgets to prevent runaway sessions on massive codebases.
- **Private repo support**: Accept a GitHub token in the request and inject it into the clone URL.
- **Concurrent clone safety**: Add `fcntl.flock` around the clone/pull logic to prevent races when the same repo is requested simultaneously.

---

## How I Used AI Coding Tools

[Fill this in with your actual experience — this section is evaluated. Be specific and honest.]

Cover:
- Which tools you used (Claude Code, Cursor, Copilot, etc.) and why
- How you approached prompting — high-level strategy, not every prompt
- Which parts of the codebase were AI-generated vs. hand-written vs. AI-assisted then edited
- How you reviewed and verified AI output before committing it
- Where AI helped most (e.g. boilerplate, serializers, migration files)
- Where it led you astray or required significant correction
- What you chose to write manually and why

Honesty is a stronger signal than a polished narrative.

---

## Limitations and Known Issues

- **Blocking requests**: Sessions longer than 30s may hit gunicorn's default timeout in production. Run with `--timeout 300` or move to async execution.
- **Private repos**: `clone_or_update_repo` has no authentication support. Private repos require SSH keys or a token in the URL.
- **Python AST only**: `get_file_summary` gives rich structural output (classes, functions, line numbers) only for `.py` files. Other languages get line count only.
- **Binary files**: Silently skipped in `read_file` and `search_code`. The agent may be confused if it asks for a binary file.
- **No clone concurrency lock**: Simultaneous requests for the same repo will race on the clone step. Acceptable for development; add `fcntl.flock` for production.
- **Unbounded repo cache**: `~/.cache/codefusion_repos/` grows with every new repo. Add a cleanup strategy for long-running deployments.
