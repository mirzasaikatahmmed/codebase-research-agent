import ast
import fnmatch
import os
from pathlib import Path

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".md", ".txt",
    ".yaml", ".yml", ".toml", ".json", ".html", ".css", ".sh", ".bash",
    ".env", ".cfg", ".ini", ".xml", ".sql",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", "dist", "build"}
DEFAULT_READ_LIMIT = 200
MAX_SEARCH_RESULTS = 30


def list_files(repo_path: str, path: str = ".") -> str:
    target = Path(repo_path) / path
    if not target.exists():
        return f"Path not found: {path}"
    if target.is_file():
        return f"{path} is a file. Use read_file to read it."

    try:
        entries = sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    except PermissionError:
        return f"Permission denied: {path}"

    lines = []
    for entry in entries:
        if entry.name.startswith(".") and entry.name != ".env.example":
            continue
        prefix = "[DIR] " if entry.is_dir() else "[FILE]"
        lines.append(f"{prefix} {entry.name}")

    return "\n".join(lines[:100]) if lines else "(empty directory)"


def read_file(
    repo_path: str, path: str, start_line: int | None = None, end_line: int | None = None
) -> str:
    full_path = Path(repo_path) / path

    if not _is_safe_path(repo_path, str(full_path)):
        return "Error: path traversal not allowed."
    if not full_path.exists():
        return f"File not found: {path}"
    if full_path.is_dir():
        return f"{path} is a directory. Use list_files instead."
    if full_path.suffix not in TEXT_EXTENSIONS and full_path.suffix != "":
        return f"Skipping binary or unsupported file: {path}"

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
    except OSError as e:
        return f"Error reading file: {e}"

    total = len(all_lines)

    if start_line and end_line:
        selected = all_lines[start_line - 1 : end_line]
        first = start_line
    elif start_line:
        selected = all_lines[start_line - 1 : start_line - 1 + DEFAULT_READ_LIMIT]
        first = start_line
    else:
        selected = all_lines[:DEFAULT_READ_LIMIT]
        first = 1

    numbered = [f"{first + i:5d} | {line}" for i, line in enumerate(selected)]
    header = f"# {path}  (total {total} lines)"
    if total > DEFAULT_READ_LIMIT and not (start_line or end_line):
        header += f"  [showing lines 1-{DEFAULT_READ_LIMIT}; use start_line/end_line for more]"

    return header + "\n" + "".join(numbered)


def search_code(repo_path: str, query: str, file_pattern: str = "") -> str:
    results = []
    query_lower = query.lower()

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in files:
            if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                continue

            filepath = Path(root) / filename
            if filepath.suffix not in TEXT_EXTENSIONS:
                continue

            try:
                with open(filepath, encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if query_lower in line.lower():
                            rel = os.path.relpath(filepath, repo_path)
                            results.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(results) >= MAX_SEARCH_RESULTS:
                                break
            except OSError:
                continue

            if len(results) >= MAX_SEARCH_RESULTS:
                break

        if len(results) >= MAX_SEARCH_RESULTS:
            break

    if not results:
        return f"No results found for '{query}'" + (f" in files matching '{file_pattern}'" if file_pattern else "")

    output = "\n".join(results)
    if len(results) == MAX_SEARCH_RESULTS:
        output += f"\n\n[Results capped at {MAX_SEARCH_RESULTS}; refine your query for more specific matches]"
    return output


def get_file_summary(repo_path: str, path: str) -> str:
    full_path = Path(repo_path) / path

    if not _is_safe_path(repo_path, str(full_path)):
        return "Error: path traversal not allowed."
    if not full_path.exists():
        return f"File not found: {path}"
    if full_path.is_dir():
        return f"{path} is a directory. Use list_files instead."

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError as e:
        return f"Error reading file: {e}"

    total_lines = content.count("\n") + 1
    summary = [f"File: {path}", f"Lines: {total_lines}"]

    if full_path.suffix == ".py":
        try:
            tree = ast.parse(content)
            classes = []
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [
                        f"    def {n.name}:{n.lineno}"
                        for n in ast.walk(node)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    classes.append(f"  class {node.name} (line {node.lineno})")
                    classes.extend(methods[:10])
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parent = _get_parent(tree, node)
                    if not isinstance(parent, ast.ClassDef):
                        functions.append(f"  def {node.name} (line {node.lineno})")

            if classes:
                summary.append("Classes:\n" + "\n".join(classes[:40]))
            if functions:
                summary.append("Top-level functions:\n" + "\n".join(functions[:30]))
        except SyntaxError:
            summary.append("(Could not parse as Python — may be Python 2 or has syntax errors)")

    return "\n".join(summary)


def _is_safe_path(base: str, path: str) -> bool:
    return os.path.abspath(path).startswith(os.path.abspath(base))


def _get_parent(tree: ast.AST, node: ast.AST) -> ast.AST | None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if child is node:
                return parent
    return None
