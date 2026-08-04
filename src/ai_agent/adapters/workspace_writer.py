"""Workspace writer with PathPolicy jail and unified-diff apply."""

from __future__ import annotations

from pathlib import Path

from ai_agent.adapters.workspace_fs import WorkspaceFS, is_within_root
from ai_agent.domain.path_policy import PathPolicy
from ai_agent.harness.diff_apply import apply_hunks_to_text, parse_unified_diff


class WorkspaceWriterFS(WorkspaceFS):
    """WorkspaceFS + policy-gated writes (implements WorkspaceWriter)."""

    def __init__(self, root: str | Path, policy: PathPolicy | None = None) -> None:
        super().__init__(root)
        self.policy = policy or PathPolicy()

    def list_paths(self, *, glob_pattern: str = "**/*", max_results: int = 200) -> list[str]:
        limit = max(1, max_results)
        out: list[str] = []
        for path in sorted(self.root.glob(glob_pattern or "**/*")):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if not is_within_root(self.root, resolved):
                continue
            rel = str(resolved.relative_to(self.root)).replace("\\", "/")
            out.append(rel)
            if len(out) >= limit:
                break
        return out

    def write_text(self, relative_path: str, content: str) -> str:
        path = self.policy.assert_writable(relative_path)
        if len(content.encode("utf-8")) > self.policy.max_file_bytes:
            raise ValueError(f"content exceeds max_file_bytes ({self.policy.max_file_bytes})")
        abs_path = Path(self.resolve_safe(path))
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        return path

    def apply_unified_diff(self, patch_text: str) -> list[str]:
        raw = patch_text.encode("utf-8")
        if len(raw) > self.policy.max_patch_bytes:
            raise ValueError(f"patch exceeds max_patch_bytes ({self.policy.max_patch_bytes})")
        patches = parse_unified_diff(patch_text)
        touched: list[str] = []
        for file_patch in patches:
            path = self.policy.assert_writable(file_patch.path)
            abs_path = Path(self.resolve_safe(path))
            if file_patch.is_deleted:
                if abs_path.is_file():
                    abs_path.unlink()
                touched.append(path)
                continue
            if file_patch.is_new or not abs_path.exists():
                original = ""
            else:
                original = abs_path.read_text(encoding="utf-8")
            updated = apply_hunks_to_text(original, file_patch.hunks)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(updated, encoding="utf-8")
            touched.append(path)
        return touched
