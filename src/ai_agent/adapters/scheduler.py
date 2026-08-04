"""File-backed scheduler + STOP kill switch for organism wake."""

from __future__ import annotations

import json
from pathlib import Path


class FileScheduler:
    """
    Persist next wake payload under ``.ai_agent/evolve/``.

    Presence of STOP file halts scheduling (kernel kill switch).
    """

    def __init__(self, root: str | Path = ".ai_agent/evolve") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.wake_path = self.root / "next_wake.json"
        self.stop_path = self.root / "STOP"

    def is_stopped(self) -> bool:
        return self.stop_path.is_file()

    def schedule_wake(self, *, at_iso: str, payload: str) -> None:
        if self.is_stopped():
            raise RuntimeError("evolve STOP file present; refusing to schedule")
        self.wake_path.write_text(
            json.dumps({"at": at_iso, "payload": payload}, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self.wake_path.is_file():
            self.wake_path.unlink()

    def read_wake(self) -> dict[str, str] | None:
        if not self.wake_path.is_file():
            return None
        raw = json.loads(self.wake_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return {str(k): str(v) for k, v in raw.items()}
