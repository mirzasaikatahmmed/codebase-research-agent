# Codebase Research Agent

A Django REST API that runs an AI agent to answer technical questions about GitHub repositories by exploring the source code directly. Research sessions, findings, and tool call logs are persisted to a database so context is reused across questions on the same repo.

---

## Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/auth/login/` | Log in (username or email + password) — sets session cookie |
| `POST` | `/api/auth/logout/` | Log out — clears session cookie |
| `POST` | `/api/sessions/` | Start a research session (clones repo, runs agent, returns answer) |
| `GET` | `/api/sessions/` | List sessions — filter by `?repo_url=` |
| `GET` | `/api/sessions/:id/` | Full session detail with findings and tool call log |
| `GET` | `/api/repos/` | List researched repositories |

**Interactive docs:**
- Swagger UI → `http://localhost:8000/api/docs/`
- ReDoc → `http://localhost:8000/api/redoc/`
- OpenAPI schema → `http://localhost:8000/api/schema/`

---

## Setup

### 1. Clone and install

```bash
git clone <this-repo>
cd codefusion-ai-task

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum
```

**SQLite (default — no extra setup):** leave `DATABASE_URL` unset.

**PostgreSQL (optional):**
```bash
# In .env:
DATABASE_URL=postgresql://user:password@localhost:5432/codefusion
```

### 3. Run migrations

```bash
python manage.py makemigrations agent
python manage.py migrate
```

### 4. Seed users and sample data

```bash
python manage.py seed_data
```

Creates 2 regular users, 1 admin superuser, and 2 sample research sessions with findings and tool call logs. **Safe to re-run** — passwords are always reset to the values below.

#### Seeded credentials

| Role | Username | Password | Email |
|------|----------|----------|-------|
| Admin | `admin` | `admin_pass123` | admin@example.com |
| User | `alice` | `alice_pass123` | alice@example.com |
| User | `bob` | `bob_pass123` | bob@example.com |

> Admin account → Django Admin at `http://localhost:8000/admin/`

### 5. Start the server

```bash
python manage.py runserver
```

---

## Authentication

The API uses **session cookie authentication**. Log in once to get a `sessionid` cookie, then pass it on every request with `-b cookies.txt`.

---

## API Reference

### `POST /api/auth/login/`

Accepts **username or email** + password. Sets a `sessionid` cookie on success.

**Request**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"username": "alice", "password": "alice_pass123"}'
```

**Response `200 OK`**
```json
{
    "detail": "Logged in.",
    "username": "alice",
    "is_staff": false
}
```

Also works with email:
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"username": "alice@example.com", "password": "alice_pass123"}'
```

**Response `401 Unauthorized`** (wrong password)
```json
{
    "detail": "Invalid credentials."
}
```

---

### `POST /api/auth/logout/`

Invalidates the session cookie.

**Request**
```bash
curl -X POST http://localhost:8000/api/auth/logout/ \
  -b cookies.txt
```

**Response `200 OK`**
```json
{
    "detail": "Logged out."
}
```

---

### `POST /api/sessions/`

Starts a research session. Clones the repo, runs the AI agent, persists all findings and tool calls, returns the complete result. **Blocks until the agent finishes** (typically 30–120 seconds).

**Request**
```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H 'Content-Type: application/json' \
  -b cookies.txt \
  -d '{
    "repo_url": "https://github.com/psf/requests",
    "question": "How does requests handle HTTP authentication internally, and what authentication methods are supported?"
  }'
```

**Response `201 Created`** *(real agent run — 22 tool calls, 6 findings, 115 500 input tokens)*
```json
{
    "id": 9,
    "repo_url": "https://github.com/psf/requests",
    "repo_name": "psf/requests",
    "question": "How does requests handle HTTP authentication internally, and what authentication methods are supported?",
    "answer": "## How Requests Handles HTTP Authentication\n\n### 1. The Auth Pipeline\nAuthentication is applied as the **last step** of request preparation in `PreparedRequest.prepare()` (`src/requests/models.py:438-443`). This ordering is intentional — it allows auth schemes like OAuth to sign a fully prepared request including headers and body.\n\n### 2. `prepare_auth()` — The Auth Dispatch Hub (`src/requests/models.py:668-695`)\n- A `(username, password)` tuple is automatically promoted to `HTTPBasicAuth`\n- Any callable implementing `AuthBase.__call__` is accepted as a custom auth handler\n- Credentials embedded in the URL (`http://user:pass@host/`) are extracted via `get_auth_from_url()` (`src/requests/utils.py:1070`)\n\n### 3. Auth Source Priority (Session Layer — `src/requests/sessions.py:536-553`)\n| Priority | Source |\n|---|---|\n| Highest | Per-request `auth=` argument |\n| Middle | Session-level `session.auth` |\n| Lowest | `.netrc` file (when `trust_env=True`) |\n\n### 4. Supported Authentication Methods\n- **HTTPBasicAuth** (`src/requests/auth.py:85-113`): Base64-encodes `username:password`, sends `Authorization: Basic <base64>`. Credentials are latin1-encoded.\n- **HTTPProxyAuth** (`src/requests/auth.py:116-121`): Subclass of HTTPBasicAuth; sets `Proxy-Authorization` header instead.\n- **HTTPDigestAuth** (`src/requests/auth.py:124-354`): Implements RFC 2617. Two-phase flow — registers `handle_401` hook; on 401, parses `WWW-Authenticate: Digest` challenge and resends request with computed digest. Supports MD5, MD5-SESS, SHA, SHA-256, SHA-512. Thread-safe via `threading.local()`.\n- **.netrc Auth** (`src/requests/utils.py:231-280`): Auto-applied when `trust_env=True`. Reads `~/.netrc` or `~/_netrc`.\n- **URL-embedded credentials** (`src/requests/utils.py:1070-1084`): `http://user:pass@example.com/` extracted by `get_auth_from_url()` → becomes HTTPBasicAuth.\n- **Custom Auth**: Any callable subclassing `AuthBase` — the extension point for OAuth, tokens, HMAC, etc.\n\n### 5. Auth on Redirects (`src/requests/sessions.py:309-332`)\n`rebuild_auth()` strips the `Authorization` header if redirected to a different hostname to prevent credential leakage. HTTP→HTTPS upgrades on standard ports on the same host are allowed to keep auth.",
    "status": "complete",
    "input_tokens": 115500,
    "output_tokens": 4428,
    "error": null,
    "started_at": "2026-05-17T23:21:20.068063Z",
    "completed_at": "2026-05-17T23:22:49.426083Z",
    "findings": [
        {
            "id": 33,
            "file_path": "src/requests/auth.py",
            "note": "Core auth module. Contains AuthBase (base class), HTTPBasicAuth (lines 85-113), HTTPProxyAuth (lines 116-121), HTTPDigestAuth (lines 124-354). _basic_auth_str helper (lines 34-75) builds Base64-encoded Basic auth header. HTTPDigestAuth uses thread-local state, hooks into response handling via handle_401 (line 273) and handle_redirect (line 268), supports MD5, MD5-SESS, SHA, SHA-256, SHA-512 algorithms.",
            "line_start": 1,
            "line_end": 354,
            "created_at": "2026-05-17T23:22:14.760759Z"
        },
        {
            "id": 34,
            "file_path": "src/requests/models.py",
            "note": "prepare_auth() method on PreparedRequest: extracts credentials from URL if no auth provided (get_auth_from_url), auto-wraps (username, password) tuple in HTTPBasicAuth, then calls auth handler as callable on self. Auth is always applied LAST in prepare().",
            "line_start": 668,
            "line_end": 695,
            "created_at": "2026-05-17T23:22:14.765846Z"
        },
        {
            "id": 35,
            "file_path": "src/requests/sessions.py",
            "note": "Session.prepare_request() merges auth from request, session-level self.auth, and .netrc (via get_netrc_auth) when trust_env=True. Auth sources are merged with merge_setting().",
            "line_start": 535,
            "line_end": 554,
            "created_at": "2026-05-17T23:22:14.768937Z"
        },
        {
            "id": 36,
            "file_path": "src/requests/sessions.py",
            "note": "rebuild_auth() on redirects: strips Authorization header if redirected to a different host (should_strip_auth), then re-applies .netrc auth if trust_env=True.",
            "line_start": 309,
            "line_end": 333,
            "created_at": "2026-05-17T23:22:14.771816Z"
        },
        {
            "id": 37,
            "file_path": "src/requests/utils.py",
            "note": "get_netrc_auth(): reads ~/.netrc or ~/_netrc (or $NETRC env var) and returns (login, password) tuple for given URL's hostname. Used automatically when trust_env=True.",
            "line_start": 231,
            "line_end": 281,
            "created_at": "2026-05-17T23:22:14.774961Z"
        },
        {
            "id": 38,
            "file_path": "src/requests/utils.py",
            "note": "get_auth_from_url(): parses username:password from URL itself (e.g. http://user:pass@host/) and returns as (str, str) tuple.",
            "line_start": 1070,
            "line_end": 1084,
            "created_at": "2026-05-17T23:22:14.778295Z"
        }
    ],
    "tool_calls": [
        {
            "id": 103,
            "tool_name": "get_previous_findings",
            "input_data": {},
            "output_data": { "result": "No previous findings for this repository." },
            "created_at": "2026-05-17T23:21:28.595998Z"
        },
        {
            "id": 104,
            "tool_name": "list_past_sessions",
            "input_data": {},
            "output_data": { "result": "No completed sessions for this repository." },
            "created_at": "2026-05-17T23:21:28.599198Z"
        },
        {
            "id": 105,
            "tool_name": "list_files",
            "input_data": { "path": "." },
            "output_data": { "result": "[DIR]  docs\n[DIR]  ext\n[DIR]  src\n[DIR]  tests\n[FILE] AUTHORS.rst\n[FILE] HISTORY.md\n[FILE] pyproject.toml\n[FILE] README.md" },
            "created_at": "2026-05-17T23:21:28.601069Z"
        },
        {
            "id": 108,
            "tool_name": "read_file",
            "input_data": { "path": "src/requests/auth.py" },
            "output_data": { "result": "# src/requests/auth.py  (total 354 lines)  [showing lines 1-200]\n    1 | \"\"\"\n    2 | requests.auth\n    ...\n   85 | class HTTPBasicAuth(AuthBase):\n  124 | class HTTPDigestAuth(AuthBase):\n  ..." },
            "created_at": "2026-05-17T23:21:37.695801Z"
        },
        {
            "id": 112,
            "tool_name": "search_code",
            "input_data": { "query": "prepare_auth", "file_pattern": "*.py" },
            "output_data": { "result": "src/requests/models.py:443:         self.prepare_auth(auth, url)\nsrc/requests/models.py:668:     def prepare_auth(\nsrc/requests/sessions.py:332:             prepared_request.prepare_auth(new_auth)" },
            "created_at": "2026-05-17T23:21:40.784095Z"
        },
        {
            "id": 124,
            "tool_name": "save_finding",
            "input_data": {
                "file_path": "src/requests/auth.py",
                "note": "Core auth module — HTTPBasicAuth, HTTPProxyAuth, HTTPDigestAuth with thread-local state",
                "line_start": 1,
                "line_end": 354
            },
            "output_data": { "result": "Finding saved: src/requests/auth.py (lines 1-354)" },
            "created_at": "2026-05-17T23:22:14.764086Z"
        }
    ]
}
```

> The agent made **22 tool calls** in this session: `get_previous_findings` → `list_past_sessions` → `list_files` → `list_files src/requests/` → `read_file auth.py` → `get_file_summary sessions.py` → `get_file_summary models.py` → `read_file auth.py (198-354)` → `search_code prepare_auth` → `read_file models.py (405-470)` → `read_file models.py (668-730)` → `read_file sessions.py (511-560)` → `read_file sessions.py (309-400)` → `search_code get_netrc_auth` → `read_file utils.py (231-290)` → `read_file sessions.py (442-510)` → `search_code get_auth_from_url` → `read_file sessions.py (127-190)` → `read_file utils.py (1070-1100)` → `search_code NETRC_FILES` → then 6× `save_finding`.

**Response `400 Bad Request`** (validation error)
```json
{
    "repo_url": ["Enter a valid URL."],
    "question": ["Ensure this field has at least 10 characters."]
}
```

---

### `GET /api/sessions/`

List all sessions, newest first. Optionally filter by repository.

**Request**
```bash
curl http://localhost:8000/api/sessions/ -b cookies.txt

# Filter by repo
curl "http://localhost:8000/api/sessions/?repo_url=https://github.com/psf/requests" \
  -b cookies.txt
```

**Response `200 OK`**
```json
[
    {
        "id": 9,
        "repo_url": "https://github.com/psf/requests",
        "question": "How does requests handle HTTP authentication internally, and what authentication methods are supported?",
        "status": "complete",
        "input_tokens": 115500,
        "output_tokens": 4428,
        "started_at": "2026-05-17T23:21:20.068063Z",
        "completed_at": "2026-05-17T23:22:49.426083Z",
        "finding_count": 6,
        "tool_call_count": 27
    },
    {
        "id": 8,
        "repo_url": "https://github.com/celery/celery",
        "question": "Where is task retry logic implemented, and what backoff strategies are supported?",
        "status": "complete",
        "input_tokens": 18500,
        "output_tokens": 780,
        "started_at": "2026-05-17T23:20:52.836673Z",
        "completed_at": "2026-05-17T23:20:52.836306Z",
        "finding_count": 2,
        "tool_call_count": 0
    },
    {
        "id": 7,
        "repo_url": "https://github.com/tiangolo/fastapi",
        "question": "How does FastAPI handle dependency injection internally?",
        "status": "complete",
        "input_tokens": 14200,
        "output_tokens": 920,
        "started_at": "2026-05-17T23:20:52.828232Z",
        "completed_at": "2026-05-17T23:20:52.827714Z",
        "finding_count": 3,
        "tool_call_count": 5
    }
]
```

---

### `GET /api/sessions/:id/`

Full session detail including answer, findings, and complete tool call log.

**Request**
```bash
curl http://localhost:8000/api/sessions/9/ -b cookies.txt
```

**Response `200 OK`** — returns the same shape as `POST /api/sessions/` above (full answer + all findings + all tool calls).

**Response `404 Not Found`**
```json
{
    "error": "Session not found."
}
```

---

### `GET /api/repos/`

List all researched repositories, ordered by most recently analyzed.

**Request**
```bash
curl http://localhost:8000/api/repos/ -b cookies.txt
```

**Response `200 OK`**
```json
[
    {
        "id": 7,
        "url": "https://github.com/psf/requests",
        "name": "requests",
        "owner": "psf",
        "last_analyzed": "2026-05-17T23:22:49.426087Z",
        "created_at": "2026-05-17T23:21:20.053938Z",
        "session_count": 1
    },
    {
        "id": 6,
        "url": "https://github.com/celery/celery",
        "name": "celery",
        "owner": "celery",
        "last_analyzed": "2026-05-17T23:20:52.833575Z",
        "created_at": "2026-05-17T23:20:52.833871Z",
        "session_count": 1
    },
    {
        "id": 5,
        "url": "https://github.com/tiangolo/fastapi",
        "name": "fastapi",
        "owner": "tiangolo",
        "last_analyzed": "2026-05-17T23:20:52.825657Z",
        "created_at": "2026-05-17T23:20:52.826219Z",
        "session_count": 1
    }
]
```

---

### Swagger UI flow

1. Open `http://localhost:8000/api/docs/`
2. Expand `POST /api/auth/login/` → Execute with your credentials
3. Click **🔒 Authorize** → select `cookieAuth (apiKey)` → Authorize
4. All subsequent Swagger requests automatically include the `sessionid` cookie

---

## Running tests

```bash
python manage.py test tests
```

---

## How it works

1. **Clone** — repo is cloned with `git clone --depth 1` into `~/.cache/codefusion_repos/`. Re-used on repeat questions (pulled to update).
2. **Agent loop** — Claude is given 7 tools and a system prompt. It calls tools in a loop until it has enough information to answer. Capped at 25 iterations to prevent infinite loops.
3. **Persistence** — every tool call and finding is written to the database during the session. On the next question about the same repo, the agent checks prior findings first before re-exploring.
4. **Context management** — tool outputs are capped at 8 KB. File reads return 200 lines by default; use `start_line`/`end_line` for specific ranges.

### Agent tools

| Tool | Purpose |
|------|---------|
| `list_files(path)` | Browse directory structure |
| `read_file(path, start_line, end_line)` | Read file contents with optional line range |
| `search_code(query, file_pattern)` | Search across repo files |
| `get_file_summary(path)` | File structure — classes/functions with line numbers (Python) |
| `save_finding(file_path, note, line_start, line_end)` | Persist a finding to the DB |
| `get_previous_findings()` | Retrieve findings from prior sessions on this repo |
| `list_past_sessions()` | List past Q&A sessions for this repo |

---

## Project structure

```
agent/
  core/
    agent.py              # Agent loop + tool dispatch (25-iteration cap, 8KB output truncation)
    prompts.py            # System prompt + 7 tool schemas
    repo_manager.py       # git clone --depth 1 with ~/.cache/ persistence
  tools/
    code_explorer.py      # list_files, read_file, search_code, get_file_summary
    db_tools.py           # save_finding, get_previous_findings, list_past_sessions
  authentication.py       # CsrfExemptSessionAuthentication (CSRF-free session auth for APIs)
  models.py               # Repository, ResearchSession, Finding, ToolCallLog
  serializers.py          # DRF serializers + OpenAPI field hints
  views.py                # LoginView, LogoutView, SessionListCreateView, SessionDetailView, RepositoryListView
  admin.py                # Django admin with Jazzmin theme + inline displays
  management/
    commands/
      seed_data.py        # Seeds 3 users + 2 sample research sessions
config/
  settings.py             # Django settings — SQLite default, PostgreSQL via DATABASE_URL
  urls.py                 # Root URLs incl. /api/docs/, /api/redoc/, /api/schema/
tests/
  test_models.py
  test_tools.py
  test_views.py
```

---

## Admin panel

Django admin is themed with **Jazzmin** (Bootstrap 5, dark sidebar).

- URL: `http://localhost:8000/admin/`
- Login: `admin` / `admin_pass123`
- Features: sidebar with icons per model, inline findings and tool call logs on session pages, search across sessions and repositories, top navbar links to API docs
