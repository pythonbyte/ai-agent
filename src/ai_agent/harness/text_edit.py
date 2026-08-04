"""Pure text-edit helpers (mutmut-friendly)."""

from __future__ import annotations


def replace_once(text: str, old: str, new: str) -> str:
    """
    Replace exactly one occurrence of ``old`` with ``new``.

    Raises ValueError if ``old`` is empty, missing, or not unique.
    """
    if not old:
        raise ValueError("old_string must be non-empty")
    count = text.count(old)
    if count == 0:
        raise ValueError("old_string not found in file")
    if count > 1:
        raise ValueError(
            f"old_string found {count} times; must be unique — include more context"
        )
    return text.replace(old, new, 1)
