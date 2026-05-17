from django.test import TestCase
from django.utils import timezone

from agent.models import Finding, Repository, ResearchSession, ToolCallLog


class RepositoryModelTest(TestCase):
    def test_create_and_str(self):
        repo = Repository.objects.create(
            url="https://github.com/tiangolo/fastapi",
            name="fastapi",
            owner="tiangolo",
        )
        self.assertEqual(str(repo), "tiangolo/fastapi")
        self.assertIsNone(repo.last_analyzed)

    def test_url_unique(self):
        Repository.objects.create(url="https://github.com/a/b", name="b", owner="a")
        with self.assertRaises(Exception):
            Repository.objects.create(url="https://github.com/a/b", name="b", owner="a")


class ResearchSessionModelTest(TestCase):
    def setUp(self):
        self.repo = Repository.objects.create(
            url="https://github.com/django/django",
            name="django",
            owner="django",
        )

    def test_default_status_and_tokens(self):
        session = ResearchSession.objects.create(repo=self.repo, question="How does ORM work?")
        self.assertEqual(session.status, ResearchSession.Status.PENDING)
        self.assertIsNone(session.answer)
        self.assertEqual(session.input_tokens, 0)
        self.assertEqual(session.output_tokens, 0)

    def test_token_accumulation(self):
        session = ResearchSession.objects.create(repo=self.repo, question="Test?")
        session.input_tokens += 1000
        session.output_tokens += 200
        session.save()
        refreshed = ResearchSession.objects.get(pk=session.pk)
        self.assertEqual(refreshed.input_tokens, 1000)
        self.assertEqual(refreshed.output_tokens, 200)

    def test_finding_relationship(self):
        session = ResearchSession.objects.create(repo=self.repo, question="Test?")
        Finding.objects.create(session=session, file_path="foo.py", note="Found something")
        self.assertEqual(session.findings.count(), 1)

    def test_tool_call_relationship(self):
        session = ResearchSession.objects.create(repo=self.repo, question="Test?")
        ToolCallLog.objects.create(
            session=session,
            tool_name="list_files",
            input_data={"path": "."},
            output_data={"result": "[FILE] foo.py"},
        )
        self.assertEqual(session.tool_calls.count(), 1)
        self.assertEqual(session.tool_calls.first().tool_name, "list_files")
