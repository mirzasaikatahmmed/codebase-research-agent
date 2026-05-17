from agent.models import Finding, Repository, ResearchSession


def save_finding(
    session: ResearchSession,
    file_path: str,
    note: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> str:
    Finding.objects.create(
        session=session,
        file_path=file_path,
        note=note,
        line_start=line_start,
        line_end=line_end,
    )
    loc = f" (lines {line_start}-{line_end})" if line_start else ""
    return f"Finding saved: {file_path}{loc}"


def get_previous_findings(repo_url: str) -> str:
    try:
        repo = Repository.objects.get(url=repo_url)
    except Repository.DoesNotExist:
        return "No previous findings for this repository."

    findings = (
        Finding.objects.filter(session__repo=repo)
        .exclude(session__status=ResearchSession.Status.FAILED)
        .order_by("-created_at")
        .select_related("session")[:50]
    )

    if not findings:
        return "No previous findings for this repository."

    lines = [f"Previous findings for {repo_url} ({findings.count()} total):"]
    for f in findings:
        loc = f" (lines {f.line_start}-{f.line_end})" if f.line_start else ""
        question_snippet = f.session.question[:60]
        lines.append(f"- [Q: {question_snippet}] {f.file_path}{loc}: {f.note}")

    return "\n".join(lines)


def list_past_sessions(repo_url: str) -> str:
    try:
        repo = Repository.objects.get(url=repo_url)
    except Repository.DoesNotExist:
        return "No past sessions for this repository."

    sessions = ResearchSession.objects.filter(
        repo=repo, status=ResearchSession.Status.COMPLETE
    ).order_by("-started_at")[:20]

    if not sessions:
        return "No completed sessions for this repository."

    lines = [f"Past sessions for {repo_url}:"]
    for s in sessions:
        date = s.started_at.strftime("%Y-%m-%d")
        lines.append(f"\n[{date}] Q: {s.question}")
        if s.answer:
            lines.append(f"  A: {s.answer[:300]}{'...' if len(s.answer) > 300 else ''}")

    return "\n".join(lines)
