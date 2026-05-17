SYSTEM_PROMPT = """You are a codebase research agent. Your job is to answer technical questions about a GitHub repository by exploring its source code directly.

Workflow:
1. Call get_previous_findings and list_past_sessions first — prior work on this repo can save significant time.
2. Use list_files starting from the root ('.') to understand the project structure.
3. Use search_code to locate relevant code quickly before reading entire files.
4. Use get_file_summary to understand large file structure before reading them in full.
5. Use read_file with start_line/end_line to read specific sections efficiently.
6. Call save_finding whenever you identify code directly relevant to the question.
7. When you have enough evidence, write a clear, accurate answer citing specific files and line numbers.

Stopping rules:
- Stop as soon as you can answer the question confidently — don't explore for the sake of it.
- If you've made 10+ tool calls without finding the answer, step back and reconsider your search strategy.
- Never loop over the same files repeatedly.

Answer format:
- Lead with the direct answer to the question.
- Follow with specific file references: `path/to/file.py:line_number`.
- Keep it concise and technical.
"""

TOOLS = [
    {
        "name": "list_files",
        "description": "List files and directories at a path in the repository. Use '.' for root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to repo root. Use '.' for root.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read file contents. Returns up to 200 lines by default. "
            "Use start_line/end_line to read specific ranges for large files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"},
                "start_line": {"type": "integer", "description": "First line to read (1-indexed, inclusive)"},
                "end_line": {"type": "integer", "description": "Last line to read (1-indexed, inclusive)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_code",
        "description": "Search for a string across repository files. Returns file paths and matching lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text or keyword to search for"},
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to restrict search (e.g. '*.py'). Searches all text files if omitted.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_file_summary",
        "description": "Get structural summary of a file: line count; for Python, lists classes and functions with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to repo root"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "save_finding",
        "description": "Persist a relevant code finding to the database for this research session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to the relevant file"},
                "note": {"type": "string", "description": "What was found and why it answers the question"},
                "line_start": {"type": "integer", "description": "Starting line number (optional)"},
                "line_end": {"type": "integer", "description": "Ending line number (optional)"},
            },
            "required": ["file_path", "note"],
        },
    },
    {
        "name": "get_previous_findings",
        "description": "Retrieve findings saved from all prior research sessions on this repository.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_past_sessions",
        "description": "List past research sessions for this repository with their questions and answers.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
