"""Bitmap design and color selection screens."""
from __future__ import annotations
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from ..codegen_service import CodegenService

from .config_screens import ConfigKeyScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class DesignScreen(Screen):
    """Grid-based bitmap editor with cursor movement, paint, fill, undo/redo."""
    base_title = "Design Mode"
    CSS = """
    #grid { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self, bitmap_data: dict):
        super().__init__()
        self.width = bitmap_data.get("bounds", {}).get("width", 10)
        self.height = bitmap_data.get("bounds", {}).get("height", 10)
        self.cursor_x = 0
        self.cursor_y = 0
        self.pixels = bitmap_data.get("bitmap", {}).get("pixels", [])
        self._key_on_enter = self.app.current_key

    @property
    def undo_stack(self):
        return self.app.history.get_undo(self.app.current_key)

    @property
    def redo_stack(self):
        return self.app.history.get_redo(self.app.current_key)

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.base_title), id="title")
        with Vertical():
            yield Static("", id="grid")
            yield Static("", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def on_mount(self) -> None:
        self.refresh_grid()
        self._update_hints()

    def on_screen_resume(self, _event) -> None:
        self.query_one("#title", Static).update(self.app.title_with_file(self.base_title))
        if self.app.current_key != self._key_on_enter:
            self._switch_to_key(self.app.current_key)
        self._update_hints()

    # Rebuild the grid display from pixel data.
    def refresh_grid(self):
        lines = []
        border = "+" + "-" * (self.width * 2) + "+"  # 2 chars per pixel in UI
        lines.append(border)
        for y in range(self.height):
            row = "|"
            for x in range(self.width):
                if x == self.cursor_x and y == self.cursor_y:
                    # Cursor: show color char with reverse video
                    pixel = self._get_pixel(x, y)
                    if pixel == " ":
                        row += "[reverse]  [/]"  # Two spaces, reversed
                    else:
                        row += f"[reverse]{pixel}{pixel}[/]"  # Color char twice, reversed
                else:
                    pixel = self._get_pixel(x, y)
                    row += pixel * 2  # Always 2 chars per pixel in UI
            row += "|"
            lines.append(row)
        lines.append(border)

        grid = "\n".join(lines)
        self.query_one("#grid").update(grid)

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    # Move cursor by arrow keys, with modifier keys for larger steps.
    def _handle_movement(self, key: str) -> bool:
        step = 1
        if key.startswith("shift"):
            step = 5
        elif key.startswith("ctrl"):
            step = 10
        elif key.startswith("alt"):
            step = 20

        if key in ("left", "h"):
            self.cursor_x = max(0, self.cursor_x - step)
        elif key in ("right", "l"):
            self.cursor_x = min(self.width - 1, self.cursor_x + step)
        elif key in ("up", "k"):
            self.cursor_y = max(0, self.cursor_y - step)
        elif key in ("down", "j"):
            self.cursor_y = min(self.height - 1, self.cursor_y + step)
        else:
            return False
        return True

    def _switch_key_dir(self, direction: str) -> None:
        dest = self.app.navigate_key(direction)
        if dest:
            self._switch_to_key(dest)
        else:
            self.show_status(f"No bitmap key to the {direction}")

    def _switch_to_key(self, new_key: str) -> None:
        old_key = self._key_on_enter
        if old_key == new_key:
            return
        self.app.history.get_undo(old_key).append((list(self.pixels), self.cursor_x, self.cursor_y))
        self.app.history.get_redo(old_key).clear()
        self.app.cursor_positions[old_key] = (self.cursor_x, self.cursor_y)
        self.app.set_current_key(new_key)
        self._key_on_enter = new_key
        bm = self.app.bitmaps.get(new_key, {})
        self.width = bm.get("bounds", {}).get("width", 10)
        self.height = bm.get("bounds", {}).get("height", 10)
        self.pixels = bm.get("bitmap", {}).get("pixels", [])
        cx, cy = self.app.cursor_positions.get(new_key, (0, 0))
        self.cursor_x = min(cx, self.width - 1)
        self.cursor_y = min(cy, self.height - 1)
        self.refresh_grid()
        self._update_hints()
        title = self.query_one("#title", Static)
        title.update(self.app.title_with_file(self.base_title))
        self.show_status(f"Switched to key {new_key}.")

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "u":
            self._undo()
            return
        if key == "ctrl+r":
            self._redo()
            return
        if key == "ctrl+k":
            self.app.push_screen(ConfigKeyScreen())
            event.stop()
            return
        if self._handle_movement(key):
            self.refresh_grid()
            return
        if key in ("d", "a", "s", "w"):
            dirs = {"d": "right", "a": "left", "s": "down", "w": "up"}
            self._switch_key_dir(dirs[key])
        elif key == "space":
            self.paint_pixel()
        elif key == "f":
            self.flood_fill()
        elif key == "c":
            self.app.push_screen(ColorScreen())
        elif key == "escape":
            self.app.pop_screen()
        elif key == "p":
            CodegenService(self.app.bitmaps, self.app.show_status).preview()

        self.refresh_grid()

    # Paint the current color at the cursor position.
    def paint_pixel(self):
        self._save_state()
        if len(self.pixels) <= self.cursor_y:
            self.pixels.extend(
                [" " * self.width for _ in range(self.cursor_y - len(self.pixels) + 1)]
            )
        row = list(self.pixels[self.cursor_y])
        if len(row) <= self.cursor_x:
            row.extend([" "] * (self.cursor_x - len(row) + 1))
        row[self.cursor_x] = " " if self.app.current_color == "0" else self.app.current_color
        self.pixels[self.cursor_y] = "".join(row)
        self.app.mark_dirty()
        self._sync_pixels()
        CodegenService(self.app.bitmaps).save_preview_html()

    # Fill a connected region from the cursor with the current color.
    def flood_fill(self):
        self._save_state()
        target = self._get_pixel(self.cursor_x, self.cursor_y)
        fill_color = self.app.current_color
        if target == fill_color:
            return
        self._flood_fill(self.cursor_x, self.cursor_y, target, fill_color)
        self.app.mark_dirty()
        self._sync_pixels()
        CodegenService(self.app.bitmaps).save_preview_html()

    def _get_pixel(self, x: int, y: int) -> str:
        if y < len(self.pixels) and x < len(self.pixels[y]):
            return self.pixels[y][x]
        return " "

    def _set_pixel(self, x: int, y: int, color: str):
        while len(self.pixels) <= y:
            self.pixels.append(" " * self.width)
        row = list(self.pixels[y])
        while len(row) <= x:
            row.append(" ")
        row[x] = " " if color == "0" else color
        self.pixels[y] = "".join(row)

    # Iterative stack-based flood fill within bounds.
    def _flood_fill(self, x: int, y: int, target: str, fill: str):
        stack = [(x, y)]
        visited = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            if cx < 0 or cx >= self.width or cy < 0 or cy >= self.height:
                continue
            if self._get_pixel(cx, cy) != target:
                continue
            visited.add((cx, cy))
            self._set_pixel(cx, cy, fill)
            stack.append((cx + 1, cy))
            stack.append((cx - 1, cy))
            stack.append((cx, cy + 1))
            stack.append((cx, cy - 1))

    # Write local pixel data back to the app's bitmap store.
    def _sync_pixels(self):
        idx = self.app.current_key
        if idx in self.app.bitmaps:
            self.app.bitmaps[idx]["bitmap"] = {"pixels": self.pixels}

    def _save_state(self):
        self.undo_stack.append((list(self.pixels), self.cursor_x, self.cursor_y))
        self.redo_stack.clear()
        self._update_hints()

    def _undo(self):
        if not self.undo_stack:
            self.show_status("Already at oldest change")
            return
        _, saved_cx, saved_cy = self.undo_stack[-1]
        self.redo_stack.append((list(self.pixels), saved_cx, saved_cy))
        self.pixels, self.cursor_x, self.cursor_y = self.undo_stack.pop()
        self._sync_pixels()
        self.app.mark_dirty()
        self._update_hints()
        self.refresh_grid()
        total = len(self.undo_stack) + len(self.redo_stack)
        self.show_status(f"Before change #{len(self.undo_stack) + 1} of {total}")

    def _redo(self):
        if not self.redo_stack:
            self.show_status("Already at newest change")
            return
        _, saved_cx, saved_cy = self.redo_stack[-1]
        self.undo_stack.append((list(self.pixels), saved_cx, saved_cy))
        self.pixels, self.cursor_x, self.cursor_y = self.redo_stack.pop()
        self._sync_pixels()
        self.app.mark_dirty()
        self._update_hints()
        self.refresh_grid()
        total = len(self.undo_stack) + len(self.redo_stack)
        self.show_status(f"After change #{len(self.undo_stack)} of {total}")

    # Refresh the hints bar with current undo/redo availability.
    def _update_hints(self):
        hints = Text()
        hints.append("[arrows/hjkl] move  ")
        hints.append("[space] paint\n")
        hints.append("[wasd] switch key\n")
        hints.append("[F]ill  ")
        hints.append("[R]ect  ")
        hints.append("[P]review\n")
        hints.append(f"[C]olor={self.app.current_color}  ")
        hints.append(f"[^K]ey={self.app.current_key}\n")
        if not self.undo_stack:
            hints.append("[U]ndo", style="dim")
        else:
            hints.append("[U]ndo")
        hints.append("  ")
        if not self.redo_stack:
            hints.append("[^R]edo", style="dim")
        else:
            hints.append("[^R]edo")
        hints.append("\n")
        hints.append("[Escape] back")
        self.query_one("#hints", Static).update(hints)


class ColorScreen(Screen):
    """Color palette selection screen (0-9, A-F)."""
    CSS = """
    #palette { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Select Color"), id="title")
        with Vertical():
            yield Static(
                "0: transparent  1: black  2: white  3: red  4: yellow\n"
                "5: green  6: cyan  7: magenta  8: orange  9: brown\n"
                "A-F: extended colors",
                id="palette"
            )
            yield Static("[0-9A-F] select  [Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key in "0123456789abcdef":
            self.app.set_current_color(key)
            self.app.pop_screen()
        elif key == "escape":
            self.app.pop_screen()
