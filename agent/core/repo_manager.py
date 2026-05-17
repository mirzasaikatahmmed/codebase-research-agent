import subprocess
from pathlib import Path

from django.conf import settings


def clone_or_update_repo(repo_url: str) -> Path:
    cache_dir: Path = settings.REPOS_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    safe_name = (
        repo_url.replace("https://github.com/", "")
        .replace("http://github.com/", "")
        .replace("/", "_")
        .replace(".", "_")
    )
    repo_path = cache_dir / safe_name

    if repo_path.exists():
        subprocess.run(
            ["git", "-C", str(repo_path), "pull", "--ff-only"],
            capture_output=True,
            timeout=30,
        )
    else:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            error = result.stderr.decode(errors="ignore")
            raise RuntimeError(f"Failed to clone repository: {error}")

    return repo_path
