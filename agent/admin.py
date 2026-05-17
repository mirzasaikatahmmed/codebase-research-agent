from django.contrib import admin
from agent.models import Repository, ResearchSession, Finding, ToolCallLog


class FindingInline(admin.TabularInline):
    model = Finding
    extra = 0
    readonly_fields = ["file_path", "note", "line_start", "line_end", "created_at"]


class ToolCallInline(admin.TabularInline):
    model = ToolCallLog
    extra = 0
    readonly_fields = ["tool_name", "input_data", "output_data", "created_at"]


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ["__str__", "url", "last_analyzed", "created_at"]
    search_fields = ["url", "name", "owner"]


@admin.register(ResearchSession)
class ResearchSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "repo", "question_short", "status", "input_tokens", "output_tokens", "started_at"]
    list_filter = ["status", "repo"]
    search_fields = ["question", "answer"]
    inlines = [FindingInline, ToolCallInline]
    readonly_fields = ["started_at", "completed_at", "input_tokens", "output_tokens"]

    def question_short(self, obj):
        return obj.question[:80]
    question_short.short_description = "Question"


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "file_path", "line_start", "created_at"]
    search_fields = ["file_path", "note"]


@admin.register(ToolCallLog)
class ToolCallLogAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "tool_name", "created_at"]
    list_filter = ["tool_name"]
