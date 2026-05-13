"""Per-key undo/redo history, session-scoped."""
from __future__ import annotations


class HistoryService:
    """Per-key undo/redo history, session-scoped."""

    def __init__(self):
        self._undo: dict[str, list] = {}
        self._redo: dict[str, list] = {}

    def get_undo(self, key: str) -> list:
        return self._undo.setdefault(key, [])

    def get_redo(self, key: str) -> list:
        return self._redo.setdefault(key, [])

    def delete(self, key: str) -> None:
        self._undo.pop(key, None)
        self._redo.pop(key, None)

    def migrate(self, old: str, new: str) -> None:
        if old in self._undo:
            self._undo[new] = self._undo.pop(old)
        if old in self._redo:
            self._redo[new] = self._redo.pop(old)

    def clear_all(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def any_nonempty(self) -> bool:
        return any(len(s) > 0 for s in self._undo.values())
