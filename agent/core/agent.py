import anthropic
from django.conf import settings
from django.utils import timezone

from agent.models import ResearchSession, ToolCallLog
from agent.tools.code_explorer import list_files, read_file, search_code, get_file_summary
from agent.tools.db_tools import save_finding, get_previous_findings, list_past_sessions
from .prompts import SYSTEM_PROMPT, TOOLS

MAX_ITERATIONS = 25
MAX_TOOL_OUTPUT_BYTES = 8192


class CodebaseResearchAgent:
    def __init__(self, repo_url: str, repo_path: str, session: ResearchSession):
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.session = session
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def run(self) -> str:
        self.session.status = ResearchSession.Status.RUNNING
        self.session.save(update_fields=["status"])

        messages = [
            {
                "role": "user",
                "content": (
                    f"Repository: {self.repo_url}\n"
                    f"Question: {self.session.question}\n\n"
                    "Start by checking previous findings, then explore the codebase to answer the question."
                ),
            }
        ]

        for _ in range(MAX_ITERATIONS):
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            self.session.input_tokens += response.usage.input_tokens
            self.session.output_tokens += response.usage.output_tokens

            if response.stop_reason == "end_turn":
                text_blocks = [b for b in response.content if b.type == "text"]
                return text_blocks[0].text if text_blocks else "No answer produced."

            if response.stop_reason != "tool_use":
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = self._process_tool_calls(response.content)
            messages.append({"role": "user", "content": tool_results})

        return "Agent reached the iteration limit without producing a final answer."

    def _process_tool_calls(self, content: list) -> list:
        results = []
        for block in content:
            if block.type != "tool_use":
                continue

            output = self._execute_tool(block.name, block.input)
            output = _truncate(output)

            ToolCallLog.objects.create(
                session=self.session,
                tool_name=block.name,
                input_data=block.input,
                output_data={"result": output},
            )

            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output}
            )

        return results

    def _execute_tool(self, name: str, params: dict) -> str:
        match name:
            case "list_files":
                return list_files(self.repo_path, params.get("path", "."))
            case "read_file":
                return read_file(
                    self.repo_path,
                    params["path"],
                    params.get("start_line"),
                    params.get("end_line"),
                )
            case "search_code":
                return search_code(
                    self.repo_path,
                    params["query"],
                    params.get("file_pattern", ""),
                )
            case "get_file_summary":
                return get_file_summary(self.repo_path, params["path"])
            case "save_finding":
                return save_finding(
                    self.session,
                    params["file_path"],
                    params["note"],
                    params.get("line_start"),
                    params.get("line_end"),
                )
            case "get_previous_findings":
                return get_previous_findings(self.repo_url)
            case "list_past_sessions":
                return list_past_sessions(self.repo_url)
            case _:
                return f"Unknown tool: {name}"


def _truncate(output: str) -> str:
    encoded = output.encode("utf-8")
    if len(encoded) <= MAX_TOOL_OUTPUT_BYTES:
        return output
    truncated = encoded[:MAX_TOOL_OUTPUT_BYTES].decode("utf-8", errors="ignore")
    return truncated + f"\n\n[Output truncated at {MAX_TOOL_OUTPUT_BYTES} bytes]"
