"""Palette data model, hardcoded presets, and resolution logic."""

HARDCODED_PRESETS: dict[str, dict] = {
    "default": {
        "name": "Default",
        "colors": {
            "0": {"glyph": " ", "hex": "#000000", "name": "transparent"},
            "1": {"glyph": ".", "hex": "#000000", "name": "black"},
            "2": {"glyph": "\u00b7", "hex": "#FFFFFF", "name": "white"},
            "3": {"glyph": "#", "hex": "#FF4A00", "name": "vermilion"},
            "4": {"glyph": "*", "hex": "#FFD24A", "name": "yellow"},
            "5": {"glyph": "+", "hex": "#5CFF4A", "name": "lime"},
            "6": {"glyph": "~", "hex": "#4AA8A8", "name": "teal"},
            "7": {"glyph": "%", "hex": "#C24AFF", "name": "purple"},
            "8": {"glyph": "@", "hex": "#FF9A00", "name": "orange"},
            "9": {"glyph": "=", "hex": "#8A4A00", "name": "brown"},
            "a": {"glyph": ":", "hex": "#0f2a66", "name": "navy"},
            "b": {"glyph": "o", "hex": "#d2d2d2", "name": "lightgray"},
            "c": {"glyph": ",", "hex": "#909090", "name": "gray"},
            "d": {"glyph": "X", "hex": "#ff7a9a", "name": "hotpink"},
            "e": {"glyph": "*", "hex": "#FFD24A", "name": "yellow"},
            "f": {"glyph": "\u00b7", "hex": "#FFFFFF", "name": "white"},
        },
    },
    "terminal": {
        "name": "Terminal",
        "colors": {
            "0": {"glyph": " ", "hex": "#000000", "name": "transparent"},
            "1": {"glyph": ".", "hex": "#000000", "name": "black"},
            "2": {"glyph": "\u2593", "hex": "#0f2a66", "name": "navy"},
            "3": {"glyph": "\u2592", "hex": "#5a5a00", "name": "olive"},
            "4": {"glyph": "\u2591", "hex": "#3fb1b1", "name": "teal"},
            "5": {"glyph": "#", "hex": "#5c2a00", "name": "sienna"},
            "6": {"glyph": "+", "hex": "#d6b07a", "name": "tan"},
            "7": {"glyph": "~", "hex": "#6ff0c8", "name": "aqua"},
            "8": {"glyph": "X", "hex": "#7a1717", "name": "maroon"},
            "9": {"glyph": "*", "hex": "#a24aff", "name": "fuchsia"},
            "a": {"glyph": "@", "hex": "#ff9a00", "name": "orange"},
            "b": {"glyph": ".", "hex": "#d2d2d2", "name": "lightgray"},
            "c": {"glyph": ":", "hex": "#909090", "name": "gray"},
            "d": {"glyph": "%", "hex": "#ff7a9a", "name": "hotpink"},
            "e": {"glyph": "=", "hex": "#ffd24a", "name": "yellow"},
            "f": {"glyph": "\u00b7", "hex": "#ffffff", "name": "white"},
        },
    },
}


def _get_root_colors() -> dict[str, dict]:
    return {k: dict(v) for k, v in HARDCODED_PRESETS["default"]["colors"].items()}


def resolve_palette(
    palette_id: str | None,
    custom_palettes: dict[str, dict] | None,
) -> dict[str, dict]:
    """Resolve a fully-populated 16-color palette dict (keys 0-F)."""
    return _resolve(palette_id, custom_palettes)[0]


def resolve_palette_with_status(
    palette_id: str | None,
    custom_palettes: dict[str, dict] | None,
) -> tuple[dict[str, dict], str | None]:
    """Like resolve_palette but returns (resolved, status_message)."""
    customs = custom_palettes or {}

    if palette_id and palette_id not in customs and palette_id not in HARDCODED_PRESETS:
        resolved = resolve_palette(None, custom_palettes)
        return resolved, f"Palette '{palette_id}' not found. Using default."

    resolved, messages = _resolve(palette_id, custom_palettes)
    status = messages[0] if messages else None
    return resolved, status


def _resolve(
    palette_id: str | None,
    custom_palettes: dict[str, dict] | None,
) -> tuple[dict[str, dict], list[str]]:
    """Internal resolve returning (palette, status_messages)."""
    customs = custom_palettes or {}
    messages: list[str] = []

    def get_def(pid: str) -> dict | None:
        if pid in customs:
            return customs[pid]
        if pid in HARDCODED_PRESETS:
            return HARDCODED_PRESETS[pid]
        return None

    def walk(pid: str, seen: set[str]) -> dict[str, dict]:
        if pid in seen:
            messages.append(f"Cycle detected in palette '{pid}', falling back to default")
            return _get_root_colors()
        seen.add(pid)
        pdef = get_def(pid)
        if pdef is None:
            return _get_root_colors()
        parent = _get_root_colors()
        inherit = pdef.get("inherit")
        if inherit:
            parent = walk(inherit, seen)
        else:
            parent = _get_root_colors()
        merged = parent.copy()
        for cid, cdef in pdef.get("colors", {}).items():
            merged[cid] = cdef
        return merged

    resolved: dict[str, dict] | None = None

    if palette_id:
        if palette_id in customs or palette_id in HARDCODED_PRESETS:
            resolved = walk(palette_id, set())

    if resolved is None and customs:
        first_key = next(iter(customs))
        resolved = walk(first_key, set())

    if resolved is None:
        resolved = _get_root_colors()

    resolved["0"] = {"glyph": " ", "hex": "#000000", "name": "transparent"}
    for entry in resolved.values():
        entry.setdefault("glyph", " ")
    return resolved, messages
