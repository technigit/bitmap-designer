from bitmap_designer.services.history_service import HistoryService


class TestHistoryService:
    def test_get_undo_empty(self):
        hs = HistoryService()
        assert hs.get_undo("foo") == []

    def test_get_redo_empty(self):
        hs = HistoryService()
        assert hs.get_redo("foo") == []

    def test_get_undo_and_redo_return_same_list(self):
        hs = HistoryService()
        u = hs.get_undo("k")
        u.append("a")
        assert hs.get_undo("k") == ["a"]

    def test_delete_removes_undo_redo(self):
        hs = HistoryService()
        hs.get_undo("k").append("a")
        hs.get_redo("k").append("b")
        hs.delete("k")
        assert hs.get_undo("k") == []
        assert hs.get_redo("k") == []

    def test_migrate_moves_undo(self):
        hs = HistoryService()
        hs.get_undo("old").append("a")
        hs.migrate("old", "new")
        assert hs.get_undo("old") == []
        assert hs.get_undo("new") == ["a"]

    def test_migrate_moves_redo(self):
        hs = HistoryService()
        hs.get_redo("old").append("b")
        hs.migrate("old", "new")
        assert hs.get_redo("old") == []
        assert hs.get_redo("new") == ["b"]

    def test_clear_all(self):
        hs = HistoryService()
        hs.get_undo("a").append(1)
        hs.get_redo("b").append(2)
        hs.clear_all()
        assert hs.get_undo("a") == []
        assert hs.get_redo("b") == []

    def test_any_nonempty_true(self):
        hs = HistoryService()
        hs.get_undo("k").append("x")
        assert hs.any_nonempty() is True

    def test_any_nonempty_false(self):
        hs = HistoryService()
        assert hs.any_nonempty() is False

    def test_migrate_key_not_present(self):
        hs = HistoryService()
        hs.migrate("nonexistent", "new")
        assert hs.get_undo("new") == []
        assert hs.get_redo("new") == []

    def test_migrate_only_undo_present(self):
        hs = HistoryService()
        hs.get_undo("old").append("a")
        hs.migrate("old", "new")
        assert hs.get_redo("new") == []
        assert hs.get_undo("new") == ["a"]

    def test_migrate_only_redo_present(self):
        hs = HistoryService()
        hs.get_redo("old").append("a")
        hs.migrate("old", "new")
        assert hs.get_undo("new") == []
        assert hs.get_redo("new") == ["a"]
