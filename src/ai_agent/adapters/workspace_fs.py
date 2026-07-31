"""Sandboxed workspace filesystem reader/searcher."""

from __future__ import annotations

from pathlib import Path

DEFAULT_MAX_FILE_BYTES = 50_000
DEFAULT_MAX_RESULTS = 20


def is_within_root(root: Path, candidate: Path) -> bool:
    """Return True if candidate resolves inside root (no path escape)."""
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class WorkspaceFS:
    """Infrastructure adapter implementing WorkspaceReader."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace root is not a directory: {self.root}")

    def resolve_safe(self, relative_path: str) -> str:
        if not relative_path or relative_path.strip() != relative_path:
            raise ValueError("Path must be a non-empty relative path")
        candidate = (self.root / relative_path).resolve()
        if not is_within_root(self.root, candidate):
            raise ValueError(f"Path escapes workspace root: {relative_path}")
        return str(candidate)

    def read_text(self, relative_path: str, *, max_bytes: int = DEFAULT_MAX_FILE_BYTES) -> str:
        path = Path(self.resolve_safe(relative_path))
        if not path.is_file():
            raise ValueError(f"Not a file: {relative_path}")
        raw = path.read_bytes()
        limit = max(1, max_bytes)
        chunk = raw[:limit]
        if b"\x00" in chunk:
            raise ValueError("File appears to be binary")
        text = chunk.decode("utf-8", errors="replace")
        if len(raw) > limit:
            return text + f"\n...[truncated at {limit} bytes]"
        return text

    def search(
        self,
        query: str,
        *,
        glob_pattern: str = "**/*",
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[tuple[str, str]]:
        if not query:
            raise ValueError("query must be non-empty")
        limit = max(1, max_results)
        hits: list[tuple[str, str]] = []
        pattern = glob_pattern or "**/*"

        for path in sorted(self.root.glob(pattern)):
            if not path.is_file():
                continue
            if not is_within_root(self.root, path.resolve()):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if query.lower() not in text.lower():
                continue
            rel = str(path.resolve().relative_to(self.root))
            snippet = _snippet(text, query)
            hits.append((rel, snippet))
            if len(hits) >= limit:
                break
        return hits


def _snippet(text: str, query: str, *, radius: int = 80) -> str:
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx < 0:
        return text[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"
