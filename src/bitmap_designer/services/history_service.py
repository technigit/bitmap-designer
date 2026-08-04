"""Per-key undo/redo history, session-scoped."""

from __future__ import annotations

_MAP_STACK_LIMIT = 50


class HistoryService:
    """Per-key undo/redo history, session-scoped."""

    def __init__(self):
        self._undo: dict[str, list] = {}
        self._redo: dict[str, list] = {}
        self._map_undo: list[dict] = []
        self._map_redo: list[dict] = []

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
        self._map_undo.clear()
        self._map_redo.clear()

    def any_nonempty(self) -> bool:
        return any(len(s) > 0 for s in self._undo.values())

    def map_record(self, snapshot: dict) -> None:
        self._map_undo.append(snapshot)
        del self._map_undo[: -_MAP_STACK_LIMIT]
        self._map_redo.clear()

    def map_undo_push(self, snapshot: dict) -> None:
        self._map_undo.append(snapshot)
        del self._map_undo[: -_MAP_STACK_LIMIT]

    def map_redo_push(self, snapshot: dict) -> None:
        self._map_redo.append(snapshot)
        del self._map_redo[: -_MAP_STACK_LIMIT]

    def map_undo_pop(self) -> dict | None:
        return self._map_undo.pop() if self._map_undo else None

    def map_redo_pop(self) -> dict | None:
        return self._map_redo.pop() if self._map_redo else None

    def map_can_undo(self) -> bool:
        return bool(self._map_undo)

    def map_can_redo(self) -> bool:
        return bool(self._map_redo)

    def map_undo_depth(self) -> int:
        return len(self._map_undo)

    def map_redo_depth(self) -> int:
        return len(self._map_redo)
