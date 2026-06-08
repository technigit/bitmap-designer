from bitmap_designer.text_utils import columnate, _visible_len


class TestVisibleLen:
    def test_plain_text(self):
        assert _visible_len("hello") == 5

    def test_textual_markup_stripped(self):
        assert _visible_len("[bold]hello[/bold]") == 5

    def test_markup_with_hex_color(self):
        assert _visible_len("[#ff0000]red[/]") == 3

    def test_empty_string(self):
        assert _visible_len("") == 0

    def test_only_markup(self):
        assert _visible_len("[bold][/bold]") == 0


class TestColumnate:
    def test_empty_rows(self):
        assert columnate([]) == ""

    def test_single_row(self):
        result = columnate([["a", "b"]])
        assert result == "a  b"

    def test_multiple_rows_aligned(self):
        rows = [
            ["name", "value"],
            ["x", "1"],
            ["yy", "22"],
        ]
        result = columnate(rows, sep="  ")
        lines = result.split("\n")
        assert lines[0] == "name  value"
        assert lines[1] == "x     1"
        assert lines[2] == "yy    22"

    def test_blank_row(self):
        rows = [
            ["a", "b"],
            ["", ""],
            ["c", "d"],
        ]
        result = columnate(rows)
        lines = result.split("\n")
        assert lines[0] == "a  b"
        assert lines[1] == ""
        assert lines[2] == "c  d"

    def test_uneven_row_lengths(self):
        rows = [
            ["a", "b", "c"],
            ["x"],
        ]
        result = columnate(rows)
        lines = result.split("\n")
        assert lines[0] == "a  b  c"
        assert lines[1] == "x     "

    def test_empty_cells(self):
        rows = [["", "b"], ["c", ""]]
        result = columnate(rows)
        lines = result.split("\n")
        assert "b" in lines[0]
        assert "c" in lines[1]

    def test_markup_in_cells(self):
        rows = [["[bold]a[/bold]", "b"], ["cc", "dd"]]
        result = columnate(rows)
        lines = result.split("\n")
        assert "[bold]a[/bold]" in lines[0]
        assert "cc" in lines[1]
