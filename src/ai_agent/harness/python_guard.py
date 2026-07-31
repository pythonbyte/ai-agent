"""Static checks for agent-authored Python before subprocess execution."""

from __future__ import annotations

import ast

# Intentionally conservative allow-by-deny for v0 (not a full OS sandbox).
BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "ssl",
        "pathlib",
        "shutil",
        "ctypes",
        "multiprocessing",
        "threading",
        "concurrent",
        "asyncio",
        "http",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "pickle",
        "shelve",
        "importlib",
        "builtins",
        "code",
        "codeop",
        "pty",
        "fcntl",
        "signal",
        "resource",
        "tempfile",
        "glob",
        "webbrowser",
        "pdb",
        "inspect",
    }
)

BLOCKED_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "help",
        "memoryview",
    }
)

MAX_CODE_CHARS = 20_000


def _root_module(name: str) -> str:
    return name.split(".", 1)[0]


def validate_python_code(source: str) -> None:
    """
    Reject clearly dangerous patterns before running code.

    Raises ValueError with a short reason when the snippet is disallowed.
    """
    cleaned = source.strip()
    if not cleaned:
        raise ValueError("code must be non-empty")
    if len(cleaned) > MAX_CODE_CHARS:
        raise ValueError(f"code exceeds max length ({MAX_CODE_CHARS} chars)")

    try:
        tree = ast.parse(cleaned)
    except SyntaxError as exc:
        raise ValueError(f"invalid Python syntax: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _root_module(alias.name)
                if root in BLOCKED_MODULES:
                    raise ValueError(f"import of blocked module: {root}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                raise ValueError("relative imports are not allowed")
            root = _root_module(node.module)
            if root in BLOCKED_MODULES:
                raise ValueError(f"import of blocked module: {root}")
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in BLOCKED_CALLS:
                raise ValueError(f"blocked call: {name}()")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise ValueError(f"blocked dunder attribute access: {node.attr}")


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None
