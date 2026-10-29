"""Shared source registry for uploads, workers and GitHub provenance."""

SOURCE_TYPE_BY_SUFFIX = {
    ".md": "markdown", ".markdown": "markdown", ".java": "java",
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "jsx",
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "tsx",
    ".go": "go", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".cs": "csharp",
}
CODE_SOURCE_TYPES = frozenset(SOURCE_TYPE_BY_SUFFIX.values()) - {"markdown"}
TASK_TYPE_BY_SOURCE = {"markdown": "markdown_parsing", **{name: "code_parsing" for name in CODE_SOURCE_TYPES}}
TASK_TYPES_BY_SOURCE = {
    "markdown": {"markdown_parsing", "knowledge_extraction"},
    **{name: {"code_parsing"} for name in CODE_SOURCE_TYPES},
}
MEDIA_TYPE_BY_SOURCE = {
    "markdown": "text/markdown", "java": "text/x-java-source", "python": "text/x-python",
    "javascript": "text/javascript", "jsx": "text/javascript", "typescript": "text/typescript",
    "tsx": "text/typescript", "go": "text/x-go", "c": "text/x-c", "cpp": "text/x-c++",
    "csharp": "text/x-csharp",
}
