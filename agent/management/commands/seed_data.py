from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from agent.models import Finding, Repository, ResearchSession, ToolCallLog

USERS = [
    {"username": "alice", "email": "alice@example.com", "password": "alice_pass123"},
    {"username": "bob", "email": "bob@example.com", "password": "bob_pass123"},
]
ADMIN = {"username": "admin", "email": "admin@example.com", "password": "admin_pass123"}


class Command(BaseCommand):
    help = "Seed users (2 regular + 1 admin) and sample research session data"

    def handle(self, *args, **options):
        self.stdout.write("Seeding users...")
        self._seed_users()
        self.stdout.write("\nSeeding research data...")
        self._seed_research_data()

        self.stdout.write(self.style.SUCCESS("\nSeed complete!"))
        self.stdout.write(f"  Users:        {User.objects.count()}")
        self.stdout.write(f"  Repositories: {Repository.objects.count()}")
        self.stdout.write(f"  Sessions:     {ResearchSession.objects.count()}")
        self.stdout.write(f"  Findings:     {Finding.objects.count()}")
        self.stdout.write(f"  Tool calls:   {ToolCallLog.objects.count()}")

    def _seed_users(self):
        for u in USERS:
            user, created = User.objects.get_or_create(
                username=u["username"],
                defaults={"email": u["email"]},
            )
            user.set_password(u["password"])
            user.is_staff = False
            user.is_superuser = False
            user.save()
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {action} user:      {u['username']}"))

        admin, created = User.objects.get_or_create(
            username=ADMIN["username"],
            defaults={"email": ADMIN["email"]},
        )
        admin.set_password(ADMIN["password"])
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"  {action} superuser: {ADMIN['username']}"))

    def _seed_research_data(self):
        # --- FastAPI repo ---
        fastapi_repo, _ = Repository.objects.get_or_create(
            url="https://github.com/tiangolo/fastapi",
            defaults={
                "name": "fastapi",
                "owner": "tiangolo",
                "last_analyzed": timezone.now(),
            },
        )

        session1, created = ResearchSession.objects.get_or_create(
            repo=fastapi_repo,
            question="How does FastAPI handle dependency injection internally?",
            defaults={
                "status": ResearchSession.Status.COMPLETE,
                "answer": (
                    "FastAPI's dependency injection is implemented in `fastapi/dependencies/utils.py`. "
                    "The core function `solve_dependencies()` (line ~475) recursively resolves dependencies "
                    "declared in function signatures using Python's `inspect` module. "
                    "Dependencies are declared via `Depends()` in `fastapi/params.py` (line ~10) and are "
                    "evaluated lazily at request time. Sync deps run inside `run_in_threadpool` when inside "
                    "an async context to avoid blocking the event loop."
                ),
                "input_tokens": 14200,
                "output_tokens": 920,
                "completed_at": timezone.now(),
            },
        )

        if created:
            Finding.objects.bulk_create([
                Finding(
                    session=session1,
                    file_path="fastapi/dependencies/utils.py",
                    note="Core dependency resolution: solve_dependencies() recursively resolves Depends() markers",
                    line_start=475,
                    line_end=560,
                ),
                Finding(
                    session=session1,
                    file_path="fastapi/params.py",
                    note="Depends() class definition — the public API for declaring dependencies",
                    line_start=10,
                    line_end=30,
                ),
                Finding(
                    session=session1,
                    file_path="fastapi/concurrency.py",
                    note="run_in_threadpool() wraps sync deps for async contexts",
                    line_start=1,
                    line_end=20,
                ),
            ])
            ToolCallLog.objects.bulk_create([
                ToolCallLog(
                    session=session1,
                    tool_name="get_previous_findings",
                    input_data={},
                    output_data={"result": "No previous findings for this repository."},
                ),
                ToolCallLog(
                    session=session1,
                    tool_name="list_files",
                    input_data={"path": "."},
                    output_data={"result": "[DIR] fastapi\n[DIR] tests\n[FILE] pyproject.toml\n[FILE] README.md"},
                ),
                ToolCallLog(
                    session=session1,
                    tool_name="search_code",
                    input_data={"query": "solve_dependencies", "file_pattern": "*.py"},
                    output_data={"result": "fastapi/dependencies/utils.py:475: async def solve_dependencies("},
                ),
                ToolCallLog(
                    session=session1,
                    tool_name="read_file",
                    input_data={"path": "fastapi/dependencies/utils.py", "start_line": 475, "end_line": 560},
                    output_data={"result": "  475 | async def solve_dependencies(\n  476 |     *,\n  477 |     request: ..."},
                ),
                ToolCallLog(
                    session=session1,
                    tool_name="save_finding",
                    input_data={
                        "file_path": "fastapi/dependencies/utils.py",
                        "note": "Core dependency resolution logic",
                        "line_start": 475,
                        "line_end": 560,
                    },
                    output_data={"result": "Finding saved: fastapi/dependencies/utils.py (lines 475-560)"},
                ),
            ])

        # --- Celery repo ---
        celery_repo, _ = Repository.objects.get_or_create(
            url="https://github.com/celery/celery",
            defaults={
                "name": "celery",
                "owner": "celery",
                "last_analyzed": timezone.now(),
            },
        )

        session2, created2 = ResearchSession.objects.get_or_create(
            repo=celery_repo,
            question="Where is task retry logic implemented, and what backoff strategies are supported?",
            defaults={
                "status": ResearchSession.Status.COMPLETE,
                "answer": (
                    "Task retry logic is primarily in `celery/app/task.py`, specifically in the `retry()` method. "
                    "Backoff strategies are controlled via the `countdown` and `max_retries` parameters. "
                    "Exponential backoff is supported via `celery/utils/backoff.py` with the `jitter()` helper. "
                    "The `autoretry_for` class attribute (defined in `celery/app/autoretry.py`) provides "
                    "declarative retry configuration with `retry_backoff`, `retry_backoff_max`, and `retry_jitter` options."
                ),
                "input_tokens": 18500,
                "output_tokens": 780,
                "completed_at": timezone.now(),
            },
        )

        if created2:
            Finding.objects.bulk_create([
                Finding(
                    session=session2,
                    file_path="celery/app/task.py",
                    note="Task.retry() method — core retry implementation with countdown and max_retries",
                    line_start=650,
                    line_end=730,
                ),
                Finding(
                    session=session2,
                    file_path="celery/app/autoretry.py",
                    note="autoretry_for decorator — declarative retry with backoff/jitter config",
                    line_start=1,
                    line_end=80,
                ),
            ])
