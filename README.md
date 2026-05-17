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

The API uses **session cookie authentication**. Login once, then pass the cookie on subsequent requests.

### Step 1 — Log in (save cookie)

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"username": "alice", "password": "alice_pass123"}'
```

Accepts either **username** (`alice`) or **email** (`alice@example.com`).

Response:
```json
{"detail": "Logged in.", "username": "alice", "is_staff": false}
```

### Step 2 — Use the cookie

```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H 'Content-Type: application/json' \
  -b cookies.txt \
  -d '{
    "repo_url": "https://github.com/tiangolo/fastapi",
    "question": "How does FastAPI handle dependency injection internally?"
  }'
```

### Step 3 — Log out

```bash
curl -X POST http://localhost:8000/api/auth/logout/ -b cookies.txt
```

### Swagger UI flow

1. Open `http://localhost:8000/api/docs/`
2. Expand `POST /api/auth/login/` → Execute with your credentials
3. Click the **🔒 Authorize** button → select `cookieAuth (apiKey)` → the browser already holds the cookie → click Authorize
4. All subsequent Swagger requests automatically include the `sessionid` cookie (`withCredentials: true`)

---

## API Usage

### Start a research session

```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H 'Content-Type: application/json' \
  -b cookies.txt \
  -d '{
    "repo_url": "https://github.com/tiangolo/fastapi",
    "question": "How does FastAPI handle dependency injection internally?"
  }'
```

The request blocks until the agent finishes (typically 30–120 seconds). The response includes the answer, all findings the agent saved, and the full tool call log.

### Get session details

```bash
curl http://localhost:8000/api/sessions/1/ -b cookies.txt
```

### List sessions for a repo

```bash
curl "http://localhost:8000/api/sessions/?repo_url=https://github.com/tiangolo/fastapi" -b cookies.txt
```

### List researched repositories

```bash
curl http://localhost:8000/api/repos/ -b cookies.txt
```

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
