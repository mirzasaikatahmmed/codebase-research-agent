from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.core.agent import CodebaseResearchAgent
from agent.core.repo_manager import clone_or_update_repo
from agent.models import Repository, ResearchSession
from agent.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    RepositorySerializer,
    ResearchSessionSerializer,
    ResearchSessionSummarySerializer,
    StartSessionSerializer,
)


def _authenticate_by_email(request, email: str, password: str):
    from django.contrib.auth.models import User
    try:
        user = User.objects.get(email__iexact=email)
        return authenticate(request, username=user.username, password=password)
    except User.DoesNotExist:
        return None


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Log in",
        description=(
            "Accepts **username or email** plus password. "
            "On success the server sets a `sessionid` cookie — Swagger UI will send it automatically "
            "on every subsequent request (`withCredentials: true`)."
        ),
        request=LoginSerializer,
        responses={
            200: LoginResponseSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=identifier, password=password)

        if user is None:
            user = _authenticate_by_email(request, identifier, password)

        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)
        return Response({"detail": "Logged in.", "username": user.username, "is_staff": user.is_staff})


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Log out",
        description="Invalidates the server-side session and clears the `sessionid` cookie.",
        responses={200: OpenApiResponse(description="Logged out successfully")},
        tags=["Auth"],
    )
    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out."})


def _parse_github_url(url: str) -> tuple[str, str]:
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return "unknown", parts[-1]


class SessionListCreateView(APIView):
    @extend_schema(
        summary="Start a research session",
        description=(
            "Clones the given GitHub repository (shallow clone), runs the AI agent to answer "
            "the question using multi-step tool calling, persists all findings and tool calls, "
            "and returns the complete session including the answer. This request blocks until "
            "the agent finishes (typically 30–120 seconds)."
        ),
        request=StartSessionSerializer,
        responses={
            201: ResearchSessionSerializer,
            400: OpenApiResponse(description="Validation error — invalid URL or question too short"),
        },
        tags=["Sessions"],
    )
    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        repo_url = serializer.validated_data["repo_url"]
        question = serializer.validated_data["question"]

        owner, name = _parse_github_url(repo_url)
        repo, _ = Repository.objects.get_or_create(
            url=repo_url,
            defaults={"name": name, "owner": owner},
        )

        session = ResearchSession.objects.create(repo=repo, question=question)

        try:
            repo_path = clone_or_update_repo(repo_url)
            agent = CodebaseResearchAgent(
                repo_url=repo_url, repo_path=str(repo_path), session=session
            )
            answer = agent.run()
            session.answer = answer
            session.status = ResearchSession.Status.COMPLETE
            session.completed_at = timezone.now()
            repo.last_analyzed = timezone.now()
            repo.save(update_fields=["last_analyzed"])
        except Exception as e:
            session.status = ResearchSession.Status.FAILED
            session.error = str(e)
        finally:
            session.save()

        return Response(ResearchSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List research sessions",
        description="Returns all research sessions, optionally filtered by repository URL. Results are ordered newest first.",
        parameters=[
            OpenApiParameter(
                name="repo_url",
                description="Filter sessions by exact repository URL (e.g. https://github.com/tiangolo/fastapi)",
                required=False,
                type=str,
            )
        ],
        responses={200: ResearchSessionSummarySerializer(many=True)},
        tags=["Sessions"],
    )
    def get(self, request):
        repo_url = request.query_params.get("repo_url")
        qs = ResearchSession.objects.select_related("repo").prefetch_related("findings", "tool_calls")
        if repo_url:
            qs = qs.filter(repo__url=repo_url)
        return Response(ResearchSessionSummarySerializer(qs, many=True).data)


class SessionDetailView(APIView):
    @extend_schema(
        summary="Get session details",
        description=(
            "Returns the full research session including the answer, all findings the agent saved, "
            "and the complete tool call log showing the agent's step-by-step reasoning."
        ),
        responses={
            200: ResearchSessionSerializer,
            404: OpenApiResponse(description="Session not found"),
        },
        tags=["Sessions"],
    )
    def get(self, request, pk):
        try:
            session = (
                ResearchSession.objects.select_related("repo")
                .prefetch_related("findings", "tool_calls")
                .get(pk=pk)
            )
        except ResearchSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ResearchSessionSerializer(session).data)


class RepositoryListView(APIView):
    @extend_schema(
        summary="List researched repositories",
        description="Returns all repositories that have been researched, ordered by most recently analyzed.",
        responses={200: RepositorySerializer(many=True)},
        tags=["Repositories"],
    )
    def get(self, request):
        repos = Repository.objects.prefetch_related("sessions")
        return Response(RepositorySerializer(repos, many=True).data)
