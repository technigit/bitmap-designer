from bitmap_designer.services.palette_service import (
    HARDCODED_PRESETS,
    resolve_palette,
    resolve_palette_with_status,
)


class TestResolvePalette:
    def test_default_palette(self):
        result = resolve_palette("default", None)
        assert result["0"]["hex"] == "#000000"
        assert result["0"]["name"] == "transparent"
        assert len(result) >= 16

    def test_terminal_palette(self):
        result = resolve_palette("terminal", None)
        assert result["0"]["hex"] == "#000000"
        assert result["0"]["name"] == "transparent"
        assert result["f"]["hex"] == "#ffffff"

    def test_none_palette_id_returns_default(self):
        result = resolve_palette(None, None)
        assert result["0"]["name"] == "transparent"

    def test_unknown_palette_id_falls_back_to_default(self):
        result = resolve_palette("nonexistent", None)
        assert result["0"]["name"] == "transparent"

    def test_custom_palette_no_inherit(self):
        custom = {
            "my_palette": {
                "name": "My Palette",
                "colors": {
                    "1": {"glyph": "X", "hex": "#FF0000", "name": "red"},
                },
            }
        }
        result = resolve_palette("my_palette", custom)
        assert result["1"]["hex"] == "#FF0000"
        assert result["1"]["name"] == "red"
        assert result["0"]["hex"] == "#000000"

    def test_custom_palette_with_inherit(self):
        custom = {
            "base": {
                "name": "Base",
                "colors": {
                    "1": {"glyph": ".", "hex": "#111111", "name": "dark"},
                },
            },
            "child": {
                "name": "Child",
                "inherit": "base",
                "colors": {
                    "2": {"glyph": "#", "hex": "#222222", "name": "light"},
                },
            },
        }
        result = resolve_palette("child", custom)
        assert result["1"]["hex"] == "#111111"
        assert result["2"]["hex"] == "#222222"

    def test_cycle_detection(self):
        custom = {
            "a": {
                "name": "A",
                "inherit": "b",
            },
            "b": {
                "name": "B",
                "inherit": "a",
            },
        }
        result, status = resolve_palette_with_status("a", custom)
        assert status is not None
        assert "cycle" in status.lower()
        assert result["0"]["name"] == "transparent"


class TestResolvePaletteWithStatus:
    def test_known_palette_no_status(self):
        result, status = resolve_palette_with_status("default", None)
        assert status is None
        assert result["0"]["name"] == "transparent"

    def test_unknown_palette_returns_status(self):
        result, status = resolve_palette_with_status("missing", None)
        assert status is not None
        assert "not found" in status.lower()
        assert result["0"]["name"] == "transparent"

    def test_first_custom_as_default_when_no_id(self):
        custom = {
            "a": {
                "name": "A",
                "colors": {"1": {"glyph": ".", "hex": "#AA0000", "name": "a"}},
            },
            "b": {
                "name": "B",
                "colors": {"2": {"glyph": "#", "hex": "#BB0000", "name": "b"}},
            },
        }
        result, status = resolve_palette_with_status(None, custom)
        assert result["1"]["hex"] == "#AA0000"


class TestHardcodedPresets:
    def test_default_preset_keys(self):
        assert "default" in HARDCODED_PRESETS
        assert "terminal" in HARDCODED_PRESETS

    def test_preset_has_name_and_colors(self):
        for preset in HARDCODED_PRESETS.values():
            assert "name" in preset
            assert "colors" in preset

    def test_each_color_has_glyph_hex_name(self):
        for preset in HARDCODED_PRESETS.values():
            for cid, cdef in preset["colors"].items():
                assert "glyph" in cdef
                assert "hex" in cdef
                assert "name" in cdef
