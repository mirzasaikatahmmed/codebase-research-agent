from django.db import models


class Repository(models.Model):
    url = models.URLField(max_length=500, unique=True)
    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)
    last_analyzed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "repositories"
        ordering = ["-last_analyzed"]

    def __str__(self):
        return f"{self.owner}/{self.name}"


class ResearchSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    repo = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="sessions")
    question = models.TextField()
    answer = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    error = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Session {self.id}: {self.question[:60]}"


class Finding(models.Model):
    session = models.ForeignKey(ResearchSession, on_delete=models.CASCADE, related_name="findings")
    file_path = models.CharField(max_length=500)
    note = models.TextField()
    line_start = models.IntegerField(null=True, blank=True)
    line_end = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.file_path}: {self.note[:60]}"


class ToolCallLog(models.Model):
    session = models.ForeignKey(ResearchSession, on_delete=models.CASCADE, related_name="tool_calls")
    tool_name = models.CharField(max_length=100)
    input_data = models.JSONField()
    output_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.tool_name} @ session {self.session_id}"
