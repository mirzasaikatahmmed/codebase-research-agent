import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from agent.models import Repository, ResearchSession


class SessionCreateTest(TestCase):
    @patch("agent.views.clone_or_update_repo")
    @patch("agent.views.CodebaseResearchAgent")
    def test_creates_session_and_returns_answer(self, MockAgent, mock_clone):
        mock_clone.return_value = "/tmp/fake_repo"
        mock_instance = MagicMock()
        mock_instance.run.return_value = "FastAPI uses Depends() for DI at request time."
        MockAgent.return_value = mock_instance

        response = self.client.post(
            "/api/sessions/",
            data=json.dumps({
                "repo_url": "https://github.com/tiangolo/fastapi",
                "question": "How does dependency injection work?",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "complete")
        self.assertEqual(data["answer"], "FastAPI uses Depends() for DI at request time.")
        self.assertIn("findings", data)
        self.assertIn("tool_calls", data)

    @patch("agent.views.clone_or_update_repo")
    @patch("agent.views.CodebaseResearchAgent")
    def test_failed_session_on_agent_error(self, MockAgent, mock_clone):
        mock_clone.return_value = "/tmp/fake_repo"
        mock_instance = MagicMock()
        mock_instance.run.side_effect = RuntimeError("Clone failed")
        MockAgent.return_value = mock_instance

        response = self.client.post(
            "/api/sessions/",
            data=json.dumps({
                "repo_url": "https://github.com/tiangolo/fastapi",
                "question": "How does dependency injection work?",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "failed")
        self.assertIn("Clone failed", data["error"])

    def test_invalid_payload_returns_400(self):
        response = self.client.post(
            "/api/sessions/",
            data=json.dumps({"repo_url": "not-a-url", "question": "short"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class SessionListTest(TestCase):
    def setUp(self):
        self.repo = Repository.objects.create(
            url="https://github.com/django/django",
            name="django",
            owner="django",
        )
        ResearchSession.objects.create(
            repo=self.repo,
            question="How does the ORM build queries?",
            status=ResearchSession.Status.COMPLETE,
        )

    def test_list_all_sessions(self):
        response = self.client.get("/api/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_filter_by_repo_url(self):
        response = self.client.get(
            "/api/sessions/",
            {"repo_url": "https://github.com/django/django"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_filter_by_unknown_repo_returns_empty(self):
        response = self.client.get("/api/sessions/", {"repo_url": "https://github.com/nope/nope"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class SessionDetailTest(TestCase):
    def setUp(self):
        self.repo = Repository.objects.create(
            url="https://github.com/django/django",
            name="django",
            owner="django",
        )
        self.session = ResearchSession.objects.create(
            repo=self.repo,
            question="How does the ORM build queries?",
            status=ResearchSession.Status.COMPLETE,
            answer="The ORM builds queries via the Query class in django/db/models/sql/query.py.",
        )

    def test_get_existing_session(self):
        response = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.session.id)
        self.assertEqual(data["status"], "complete")

    def test_get_nonexistent_session(self):
        response = self.client.get("/api/sessions/99999/")
        self.assertEqual(response.status_code, 404)


class RepositoryListTest(TestCase):
    def test_empty_list(self):
        response = self.client.get("/api/repos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_lists_repos(self):
        Repository.objects.create(
            url="https://github.com/tiangolo/fastapi",
            name="fastapi",
            owner="tiangolo",
        )
        response = self.client.get("/api/repos/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["name"], "fastapi")
