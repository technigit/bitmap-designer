"""Palette editing screens: create, delete, edit color slots."""
from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.widgets import Static, Input
from textual.containers import Vertical

from .popup_screen import PopupScreen
from ..constants import HINT_ESCAPE
from ..palette_service import HARDCODED_PRESETS

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class ConfigPaletteCreateScreen(PopupScreen):
    """Prompt for new palette ID, creates with template from current palette."""
    base_title = "Create Palette"
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static("New palette ID (no spaces):", id="prompt")
            self.input = Input(value="", placeholder="my-palette", id="new-palette-id")
            yield self.input
            yield Static("[Enter] create  " + HINT_ESCAPE, id="hints", markup=False)
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            pid = (self.input.value or "").strip()
            if not pid or " " in pid:
                self.show_status("Please enter a valid ID (no spaces).")
                return
            if pid in self.app.custom_palettes or pid in HARDCODED_PRESETS:
                self.show_status(f"Palette '{pid}' already exists.")
                return
            template = self.app.active_palette
            colors = {}
            for cid in "123456789abcdef":
                entry = template.get(cid, {})
                colors[cid] = {
                    "glyph": entry.get("glyph", " "),
                    "hex": entry.get("hex", "#000000"),
                    "name": entry.get("name", "?"),
                }
            new_palettes = dict(self.app.custom_palettes)
            new_palettes[pid] = {
                "inherit": self.app.palette_id or "default",
                "name": pid,
                "colors": colors,
            }
            self.app.set_custom_palettes(new_palettes)
            self.app.set_palette(pid)
            self.app.pop_screen()
            self.app.show_status(f"Palette '{pid}' created.")


class ConfigPaletteDeleteConfirmScreen(PopupScreen):
    """Confirm deletion of a custom palette."""
    base_title = "Delete Palette"

    def __init__(self, palette_id: str):
        super().__init__()
        self.palette_id = palette_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(
                f"Delete palette '{self.palette_id}'?",
                id="prompt"
            )
            yield Static("[Y]es  [N]o  " + HINT_ESCAPE, id="hints", markup=False)
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        k = event.key.lower()
        if k == "y":
            new_palettes = dict(self.app.custom_palettes)
            if self.palette_id in new_palettes:
                del new_palettes[self.palette_id]
                self.app.set_custom_palettes(new_palettes)
                if self.app.palette_id == self.palette_id:
                    self.app.set_palette(None)
                self.app.pop_screen()
                self.app.show_status(f"Palette '{self.palette_id}' deleted.")
        elif k in ("n", "escape"):
            self.app.pop_screen()


class ConfigPaletteEditScreen(PopupScreen):
    """Edit color slots of a custom palette."""
    base_title = "Edit Palette"
    CSS = """
    #color-list { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self, palette_id: str):
        super().__init__()
        self.palette_id = palette_id
        self._cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static("", id="color-list")
            yield Static(
                "[j/k/up/down] navigate  [Enter] edit slot  "
                + HINT_ESCAPE,
                id="hints", markup=False
            )
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_mount(self) -> None:
        self._update_display()

    def on_screen_resume(self, _event) -> None:
        self._update_display()

    def _get_palette_colors(self) -> dict[str, dict]:
        pal = self.app.custom_palettes.get(self.palette_id, {})
        return pal.get("colors", {})

    def _update_display(self):
        pal = self.app.active_palette
        custom_colors = self._get_palette_colors()
        lines = [f"Palette: {self.palette_id}"]
        for i in range(16):
            cid = format(i, "x")
            entry = pal.get(cid, {"glyph": " ", "hex": "#000000", "name": "?"})
            hex_color = entry["hex"]
            glyph_display = entry["glyph"]
            name = entry["name"]
            inherited = cid not in custom_colors
            inherited_mark = " (inherited)" if inherited else ""
            cursor_mark = " >" if i == self._cursor else "  "
            label = (
                f"{cursor_mark}{cid.upper()}: {name}  "
                f"glyph={glyph_display}  hex={hex_color}{inherited_mark}"
            )
            lines.append(label)
        self.query_one("#color-list", Static).update("\n".join(lines))

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        k = event.key.lower()
        if k in ("j", "down") and self._cursor < 15:
            self._cursor += 1
            self._update_display()
        elif k in ("k", "up") and self._cursor > 0:
            self._cursor -= 1
            self._update_display()
        elif k in ("enter", "\n"):
            cid = format(self._cursor, "x")
            if cid == "0":
                self.show_status("Color 0 is reserved transparent.")
                return
            self.app.push_screen(
                ConfigPaletteColorEditScreen(self.palette_id, cid)
            )
        elif k == "escape":
            self.app.pop_screen()


class ConfigPaletteColorEditScreen(PopupScreen):
    """Edit a single color slot's hex, char, and name."""

    def __init__(self, palette_id: str, color_id: str):
        super().__init__()
        self.palette_id = palette_id
        self.color_id = color_id
        self._field = 0  # 0=hex, 1=char, 2=name
        self.input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                f"Edit color {self.color_id.upper()}",
                id="title"
            )
            yield Static("", id="prompt")
            self.input = Input(value="", id="slot-input")
            yield self.input
            yield Static(
                "[Enter] next  [Escape] cancel",
                id="hints", markup=False
            )
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_mount(self) -> None:
        self._start_field()

    def _start_field(self):
        fields = ["hex", "glyph", "name"]
        self.query_one("#prompt", Static).update(
            f"Enter {fields[self._field]} (leave blank to skip):"
        )
        current_colors = self.app.custom_palettes.get(
            self.palette_id, {}
        ).get("colors", {})
        current = current_colors.get(self.color_id, {})
        current_val = {
            "hex": current.get("hex", ""),
            "glyph": current.get("glyph", ""),
            "name": current.get("name", ""),
        }.get(fields[self._field], "")
        self.input.value = current_val
        self.input.focus()

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            fields = ["hex", "glyph", "name"]
            val = self.input.value.strip()
            new_palettes = dict(self.app.custom_palettes)
            pal = dict(new_palettes.get(self.palette_id, {}))
            colors = dict(pal.get("colors", {}))
            cdef = dict(colors.get(self.color_id, {}))
            if val:
                cdef[fields[self._field]] = val
            colors[self.color_id] = cdef
            pal["colors"] = colors
            new_palettes[self.palette_id] = pal
            self.app.set_custom_palettes(new_palettes)
            self._field += 1
            if self._field >= 3:
                self.app.pop_screen()
            else:
                self._start_field()
