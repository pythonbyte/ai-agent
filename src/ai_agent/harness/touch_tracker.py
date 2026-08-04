"""Track files touched by engineer edit tools for scoped commits."""

from __future__ import annotations


class TouchTracker:
    """Collect relative paths modified during an evolve/engineer session."""

    def __init__(self) -> None:
        self._paths: set[str] = set()

    def record(self, path: str) -> None:
        cleaned = path.strip().replace("\\", "/")
        if cleaned:
            self._paths.add(cleaned)

    def record_many(self, paths: list[str]) -> None:
        for path in paths:
            self.record(path)

    def paths(self) -> list[str]:
        return sorted(self._paths)

    def clear(self) -> None:
        self._paths.clear()
