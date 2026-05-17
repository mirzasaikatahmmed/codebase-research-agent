from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from agent.models import Finding, Repository, ResearchSession, ToolCallLog


class RepositorySerializer(serializers.ModelSerializer):
    session_count = serializers.SerializerMethodField()

    class Meta:
        model = Repository
        fields = ["id", "url", "name", "owner", "last_analyzed", "created_at", "session_count"]

    @extend_schema_field(serializers.IntegerField())
    def get_session_count(self, obj):
        return obj.sessions.count()


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = ["id", "file_path", "note", "line_start", "line_end", "created_at"]


class ToolCallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolCallLog
        fields = ["id", "tool_name", "input_data", "output_data", "created_at"]


class ResearchSessionSerializer(serializers.ModelSerializer):
    repo_url = serializers.CharField(source="repo.url", read_only=True)
    repo_name = serializers.CharField(source="repo.__str__", read_only=True)
    findings = FindingSerializer(many=True, read_only=True)
    tool_calls = ToolCallLogSerializer(many=True, read_only=True)

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "repo_url",
            "repo_name",
            "question",
            "answer",
            "status",
            "input_tokens",
            "output_tokens",
            "error",
            "started_at",
            "completed_at",
            "findings",
            "tool_calls",
        ]


class ResearchSessionSummarySerializer(serializers.ModelSerializer):
    repo_url = serializers.CharField(source="repo.url", read_only=True)
    finding_count = serializers.SerializerMethodField()
    tool_call_count = serializers.SerializerMethodField()

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "repo_url",
            "question",
            "status",
            "input_tokens",
            "output_tokens",
            "started_at",
            "completed_at",
            "finding_count",
            "tool_call_count",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_finding_count(self, obj):
        return obj.findings.count()

    @extend_schema_field(serializers.IntegerField())
    def get_tool_call_count(self, obj):
        return obj.tool_calls.count()


class StartSessionSerializer(serializers.Serializer):
    repo_url = serializers.URLField()
    question = serializers.CharField(min_length=10)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})


class LoginResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    username = serializers.CharField()
    is_staff = serializers.BooleanField()
