"""Bitmap design and color selection screens."""
from __future__ import annotations
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from .popup_screen import PopupScreen
from ..codegen_service import CodegenService
from ..constants import create_default_bitmap
from ..text_utils import columnate

from .command_bar import handle_cmd_key
from .config_screens import ConfigKeyScreen
from .map_screen import MapScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class DesignScreen(Screen):
    """Grid-based bitmap editor with cursor movement, paint, fill, undo/redo."""
    base_title = "Design Mode"
    CSS = """
    #grid { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; margin-left: 3; }
    """

    def __init__(self, bitmap_data: dict):
        super().__init__()
        self.width = bitmap_data.get("bounds", {}).get("width", 10)
        self.height = bitmap_data.get("bounds", {}).get("height", 10)
        self.cursor_x = 0
        self.cursor_y = 0
        self.pixels = bitmap_data.get("bitmap", {}).get("pixels", [])
        self._key_on_enter = self.app.current_key
        self.offset_x: int = 0
        self.offset_y: int = 0
        self.viewport = [0, 0]
        self.scroll_mode = False
        self.rect_mode = False
        self.rect_start = [0, 0]
        self.cmd_mode = False
        self.cmd_buffer = ""
        self._last_boundary_msg = False

    @property
    def undo_stack(self):
        return self.app.history.get_undo(self.app.current_key)

    @property
    def redo_stack(self):
        return self.app.history.get_redo(self.app.current_key)

    # Recalculate viewport dimensions based on available screen space.
    def _recalc_viewport(self):
        self.viewport[0] = max(1, (self.size.width - 8) // 2)
        self.viewport[1] = max(1, self.size.height - 14)
        self._clamp_offset()

    # Clamp offset so viewport stays within bitmap bounds.
    def _clamp_offset(self):
        self.offset_x = max(0, min(self.offset_x, max(0, self.width - self.viewport[0])))
        self.offset_y = max(0, min(self.offset_y, max(0, self.height - self.viewport[1])))

    @property
    def content_fits(self) -> bool:
        return self.viewport[0] >= self.width and self.viewport[1] >= self.height

    # Adjust offset to keep cursor at least 2px from viewport edge.
    def _ensure_cursor_visible(self):
        margin = 2
        if self.viewport[0] >= self.width and self.viewport[1] >= self.height:
            self.offset_x = 0
            self.offset_y = 0
            return
        if self.cursor_x < self.offset_x + margin:
            self.offset_x = max(0, self.cursor_x - margin)
        elif self.cursor_x >= self.offset_x + self.viewport[0] - margin:
            self.offset_x = min(
                max(0, self.width - self.viewport[0]),
                self.cursor_x - self.viewport[0] + margin + 1
            )
        if self.cursor_y < self.offset_y + margin:
            self.offset_y = max(0, self.cursor_y - margin)
        elif self.cursor_y >= self.offset_y + self.viewport[1] - margin:
            self.offset_y = min(
                max(0, self.height - self.viewport[1]),
                self.cursor_y - self.viewport[1] + margin + 1
            )

    # Shift the viewport by (dx, dy) bitmap pixels. Returns True if offset changed.
    def _scroll(self, dx: int, dy: int) -> bool:
        old_x, old_y = self.offset_x, self.offset_y
        self.offset_x = max(0, min(self.offset_x + dx, max(0, self.width - self.viewport[0])))
        self.offset_y = max(0, min(self.offset_y + dy, max(0, self.height - self.viewport[1])))
        return self.offset_x != old_x or self.offset_y != old_y

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.base_title), id="title")
        with Vertical():
            yield Static("", id="grid")
            yield Static("", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def on_mount(self) -> None:
        ox, oy = self.app.scroll_offsets.get(self.app.current_key, (0, 0))
        self.offset_x, self.offset_y = ox, oy
        self.refresh_grid()
        self.update_hints()

    def _in_rect_selection(self, x: int, y: int) -> bool:
        if not self.rect_mode:
            return False
        x1 = min(self.rect_start[0], self.cursor_x)
        x2 = max(self.rect_start[0], self.cursor_x)
        y1 = min(self.rect_start[1], self.cursor_y)
        y2 = max(self.rect_start[1], self.cursor_y)
        return x1 <= x <= x2 and y1 <= y <= y2

    def _cell_markup(self, x: int, y: int, *, rect_preview: bool = False) -> str:
        if rect_preview:
            char = self.app.current_color
        else:
            char = self._get_pixel(x, y)
        color_entry = self.app.active_palette.get(char, {})
        hex_color = color_entry.get("hex", "")
        display_char = (
            color_entry.get("glyph", char) if self.app.glyphmode else char
        )
        cursor = (x == self.cursor_x and y == self.cursor_y)

        if char == " ":
            if cursor:
                return "[reverse]  [/]"
            return "  "

        if cursor:
            return f"[reverse]{display_char}{display_char}[/]"

        if self.app.color_pixels == "on":
            return f"[on {hex_color}]  [/]"
        if self.app.color_pixels == "mixed":
            return f"[{hex_color}]{display_char}{display_char}[/]"
        return f"{display_char}{display_char}"

    def on_screen_resume(self, _event) -> None:
        self.scroll_mode = False
        self.rect_mode = False
        self.query_one("#title", Static).update(self.app.title_with_file(self.base_title))
        if self.app.current_key != self._key_on_enter:
            self.switch_to_key(self.app.current_key)
        else:
            bm = self.app.bitmaps.get(self.app.current_key, create_default_bitmap())
            self.width = bm["bounds"]["width"]
            self.height = bm["bounds"]["height"]
            self.pixels = bm["bitmap"]["pixels"]
            self._ensure_cursor_visible()
            self.refresh_grid()
        self.update_hints()

    # Rebuild the grid display from pixel data.
    def refresh_grid(self):
        self._recalc_viewport()
        vp_w = min(self.viewport[0], self.width - self.offset_x)
        vp_h = min(self.viewport[1], self.height - self.offset_y)

        scrolled_l = self.offset_x > 0
        scrolled_r = self.offset_x + vp_w < self.width
        scrolled_u = self.offset_y > 0
        scrolled_d = self.offset_y + vp_h < self.height

        lines = [" " + self.app.current_key]
        lines.append(self._border_line(vp_w, scrolled_l, scrolled_r))
        lines.extend(self._grid_lines(vp_w, vp_h, scrolled_u, scrolled_d))
        lines.append(self._border_line(vp_w, scrolled_l, scrolled_r))
        self.query_one("#grid").update("\n".join(lines))

    def _border_line(self, vp_w: int, sl: bool, sr: bool) -> str:
        line = "+"
        if sl and sr:
            line += "<" + "-" * max(0, vp_w * 2 - 2) + ">"
        elif sl:
            line += "<" + "-" * max(0, vp_w * 2 - 1)
        elif sr:
            line += "-" * max(0, vp_w * 2 - 1) + ">"
        else:
            line += "-" * (vp_w * 2)
        line += "+"
        return line

    def _grid_lines(self, vp_w: int, vp_h: int,
                    su: bool, sd: bool) -> list[str]:
        rows = []
        for i in range(vp_h):
            y = self.offset_y + i
            indicator = ("^" if (su and i == 0)
                         else "v" if (sd and i == vp_h - 1)
                         else "|")
            row = indicator
            for j in range(vp_w):
                x = self.offset_x + j
                row += self._cell_markup(x, y, rect_preview=self._in_rect_selection(x, y))
            row += indicator
            rows.append(row)
        return rows

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _clear_boundary_status(self):
        if self._last_boundary_msg:
            self.query_one("#status", Static).update("")
            self._last_boundary_msg = False

    # Move cursor or scroll by arrow/hjkl keys, applying step and scroll mode.
    def _handle_movement(self, key: str) -> bool:
        boundary_msgs = {
            "left": "Already at left edge",
            "h": "Already at left edge",
            "right": "Already at right edge",
            "l": "Already at right edge",
            "up": "Already at top edge",
            "k": "Already at top edge",
            "down": "Already at bottom edge",
            "j": "Already at bottom edge",
        }
        parts = key.split("+")
        base = parts[-1]
        base_lower = base.lower()

        if base_lower not in ("left", "right", "up", "down", "h", "j", "k", "l"):
            return False

        mods = set(parts[:-1])
        if base.isupper():
            mods.add("shift")
        step = self.app.step * (5 if "shift" in mods else 1)

        if self.scroll_mode:
            self._scroll_move(base_lower, step, boundary_msgs)
        else:
            self._cursor_move(base_lower, step, boundary_msgs)
            self._ensure_cursor_visible()

        return True

    def _scroll_move(self, base_lower: str, step: int, msgs: dict) -> None:
        deltas = {
            "left": (-step, 0), "h": (-step, 0),
            "right": (step, 0), "l": (step, 0),
            "up": (0, -step), "k": (0, -step),
            "down": (0, step), "j": (0, step),
        }
        dx, dy = deltas[base_lower]
        if not self._scroll(dx, dy):
            self.show_status(msgs[base_lower])
            self._last_boundary_msg = True
        else:
            self._clear_boundary_status()

    def _cursor_move(self, base_lower: str, step: int, msgs: dict) -> None:
        if base_lower in ("left", "h"):
            nx = max(0, self.cursor_x - step)
            if nx == self.cursor_x:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor_x = nx
        elif base_lower in ("right", "l"):
            nx = min(self.width - 1, self.cursor_x + step)
            if nx == self.cursor_x:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor_x = nx
        elif base_lower in ("up", "k"):
            ny = max(0, self.cursor_y - step)
            if ny == self.cursor_y:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor_y = ny
        elif base_lower in ("down", "j"):
            ny = min(self.height - 1, self.cursor_y + step)
            if ny == self.cursor_y:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor_y = ny
        self._clear_boundary_status()

    def on_resize(self) -> None:
        self.refresh_grid()

    def _on_key_rect_mode(self, key: str) -> None:
        k_low = key.lower()
        if k_low in ("left", "right", "up", "down", "h", "j", "k", "l"):
            parts = key.split("+")
            base = parts[-1]
            base_low = base.lower()
            mods = set(parts[:-1])
            if base.isupper():
                mods.add("shift")
            step = self.app.step * (5 if "shift" in mods else 1)
            if base_low in ("left", "h"):
                self.cursor_x = max(0, self.cursor_x - step)
            elif base_low in ("right", "l"):
                self.cursor_x = min(self.width - 1, self.cursor_x + step)
            elif base_low in ("up", "k"):
                self.cursor_y = max(0, self.cursor_y - step)
            elif base_low in ("down", "j"):
                self.cursor_y = min(self.height - 1, self.cursor_y + step)
            self._ensure_cursor_visible()
            self.refresh_grid()
            return
        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            setattr(self.app, 'step', int(key))
            self.show_status(f"Step set to {self.app.step}")
            self.update_hints()
            return
        if k_low in ("enter", "\n"):
            self._paint_rectangle()
            self.rect_mode = False
            self.show_status("Rectangle painted")
            self.update_hints()
            self.refresh_grid()
            return
        if k_low == "escape":
            self.cursor_x = self.rect_start[0]
            self.cursor_y = self.rect_start[1]
            self.rect_mode = False
            self.show_status("Rectangle cancelled")
            self.update_hints()
            self.refresh_grid()
            return

    def _on_key_action(self, k: str, event) -> None:
        if k == "u":
            self._undo()
            return
        if k == "ctrl+r":
            self._redo()
            return
        if k in ("slash", "solidus"):
            self.app.push_screen(ConfigKeyScreen())
            event.stop()
            return
        if self._handle_movement(event.key):
            self.refresh_grid()
            return
        self._on_key_shortcut(k)

    def _on_key_shortcut(self, k: str) -> None:
        if k in ("d", "a", "s", "w"):
            dirs = {"d": "right", "a": "left", "s": "down", "w": "up"}
            self._switch_key_dir(dirs[k])
        elif k == "space":
            self.paint_pixel()
        elif k == "f":
            self.flood_fill()
        elif k == "r":
            self.rect_mode = True
            self.rect_start[0] = self.cursor_x
            self.rect_start[1] = self.cursor_y
            self.update_hints()
            self.show_status("Rectangle mode: select opposite corner, "
                             "[Enter] confirm, [Escape] cancel")
            self.refresh_grid()
            return
        elif k == "c":
            self.app.push_screen(ColorScreen())
        elif k == "escape":
            if self.scroll_mode:
                self.scroll_mode = False
                self.show_status("Exited scroll mode")
                self.update_hints()
                return
            self.app.pop_screen()
        elif k == "p":
            svc = CodegenService(
                self.app.bitmaps, self.app.show_status, palette=self.app.active_palette
            )
            svc.preview()
        elif k == "m":
            self.app.push_screen(MapScreen())

        self.refresh_grid()

    def _switch_key_dir(self, direction: str) -> None:
        dest = self.app.navigate_key(direction)
        if dest:
            self.switch_to_key(dest)
        else:
            msgs = {
                "right": "No bitmap key to the right",
                "left": "No bitmap key to the left",
                "down": "No bitmap key below",
                "up": "No bitmap key above",
            }
            self.show_status(msgs[direction])

    def switch_to_key(self, new_key: str) -> None:
        old_key = self._key_on_enter
        if old_key == new_key:
            return
        self.rect_mode = False
        self.app.cursor_positions[old_key] = (self.cursor_x, self.cursor_y)
        self.app.scroll_offsets[old_key] = (self.offset_x, self.offset_y)
        self.app.set_current_key(new_key)
        self._key_on_enter = new_key
        bm = self.app.bitmaps.get(new_key, {})
        self.width = bm.get("bounds", {}).get("width", 10)
        self.height = bm.get("bounds", {}).get("height", 10)
        self.pixels = bm.get("bitmap", {}).get("pixels", [])
        cx, cy = self.app.cursor_positions.get(new_key, (0, 0))
        self.cursor_x = min(cx, self.width - 1)
        self.cursor_y = min(cy, self.height - 1)
        ox, oy = self.app.scroll_offsets.get(new_key, (0, 0))
        self.offset_x, self.offset_y = ox, oy
        self.refresh_grid()
        self.update_hints()
        title = self.query_one("#title", Static)
        title.update(self.app.title_with_file(self.base_title))
        self.show_status(f"Switched to key {new_key}.")

    def on_key(self, event) -> None:
        if handle_cmd_key(self, event):
            event.stop()
            return

        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return

        key = event.key

        if self.rect_mode:
            self._on_key_rect_mode(key)
            return

        if key == "g":
            if self.content_fits:
                self.show_status("All content visible — scrolling disabled")
                return
            self.scroll_mode = not self.scroll_mode
            if self.scroll_mode:
                self.show_status("Scroll mode on")
            else:
                self.show_status("Scroll mode off")
            self.update_hints()
            return

        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            setattr(self.app, 'step', int(key))
            self.show_status(f"Step set to {self.app.step}")
            self.update_hints()
            return

        self._on_key_action(key.lower(), event)

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
        CodegenService(self.app.bitmaps, palette=self.app.active_palette).save_preview_html()

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
        CodegenService(self.app.bitmaps, palette=self.app.active_palette).save_preview_html()

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

    def _paint_rectangle(self):
        self._save_state()
        x1 = min(self.rect_start[0], self.cursor_x)
        x2 = max(self.rect_start[0], self.cursor_x)
        y1 = min(self.rect_start[1], self.cursor_y)
        y2 = max(self.rect_start[1], self.cursor_y)
        fill = self.app.current_color
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self._set_pixel(x, y, fill)
        self.app.mark_dirty()
        self._sync_pixels()
        CodegenService(self.app.bitmaps, palette=self.app.active_palette).save_preview_html()



    def _save_state(self):
        self.undo_stack.append((list(self.pixels), self.cursor_x, self.cursor_y))
        self.redo_stack.clear()
        self.update_hints()

    def _sync_pixels(self) -> None:
        key = self.app.current_key
        if key in self.app.bitmaps:
            self.app.bitmaps[key]["bitmap"]["pixels"] = list(self.pixels)
            self.app.mark_dirty()

    def _undo(self):
        if not self.undo_stack:
            self.show_status("Already at oldest change")
            return
        _, saved_cx, saved_cy = self.undo_stack[-1]
        self.redo_stack.append((list(self.pixels), saved_cx, saved_cy))
        self.pixels, self.cursor_x, self.cursor_y = self.undo_stack.pop()
        self._sync_pixels()
        self.app.mark_dirty()
        self.update_hints()
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
        self.update_hints()
        self.refresh_grid()
        total = len(self.undo_stack) + len(self.redo_stack)
        self.show_status(f"After change #{len(self.undo_stack)} of {total}")

    # Refresh the hints bar with current undo/redo availability.
    def update_hints(self):
        hints = Text()
        if self.rect_mode:
            hints.append("[arrows/hjkl] select opposite corner  ")
            hints.append(f"[1-9] step={self.app.step}\n")
            hints.append("[Enter] confirm  [Escape] cancel  ")
            hints.append(f"[C]olor={self.app.current_color}", style="dim")
            hints.append("  [space] paint", style="dim")
            hints.append("  [F]ill", style="dim")
            hints.append("  [U]ndo", style="dim")
            hints.append("  [^R]edo", style="dim")
            hints.append("\n")
            hints.append("[wasd] switch key", style="dim")
            hints.append("  [/] find key", style="dim")
            hints.append("  [g] scroll", style="dim")
            hints.append("  [M]ap", style="dim")
            hints.append("  [P]review", style="dim")
        else:
            hints.append(f"[C]olor={self.app.current_color}  ")
            hints.append("[space] paint  ")
            hints.append("[F]ill  ")
            hints.append("[R]ect  ")
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
            if self.scroll_mode:
                hints.append("[arrows/hjkl] scroll  [Esc] exit scroll  ")
            else:
                hints.append("[arrows/hjkl] move  ")
                hints.append("[g] scroll  ", style="dim" if self.content_fits else None)
            hints.append(f"[1-9] step={self.app.step}\n")
            if len(self.app.bitmaps) <= 1:
                hints.append("[wasd] switch key  ", style="dim")
            else:
                hints.append("[wasd] switch key  ")
            hints.append("[/] find key\n")
            hints.append("[M]ap  ")
            hints.append("[P]review  ")
            hints.append("[Escape] back")
        self.query_one("#hints", Static).update(hints)


class ColorScreen(PopupScreen):
    """Color palette selection screen (0-F)."""
    CSS = """
    #palette { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file("Select Color"), id="title")
            yield Static("", id="palette")
            yield Static("[0-9A-F] select  [Escape] cancel", id="hints", markup=False)
            yield Static("", id="status")

    def on_mount(self) -> None:
        self._refresh()

    def on_screen_resume(self, _event) -> None:
        self._refresh()

    def _refresh(self):
        pal = self.app.active_palette
        rows = []
        for i in range(16):
            cid = format(i, "x")
            entry = pal.get(cid, {"glyph": " ", "hex": "#000000", "name": "?"})
            hex_color = entry.get("hex", "#000000")
            glyph_display = entry.get("glyph", " ")
            name = entry.get("name", "?")
            asterisk = "* " if cid == self.app.current_color else "  "
            rows.append((
                f"{asterisk}{cid.upper()}:",
                name,
                f"({glyph_display})",
                f"[{hex_color}]{cid.upper()}[/]",
            ))
        self.query_one("#palette", Static).update(
            columnate(rows, sep="  ")
        )

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        key = event.key.lower()
        if key in "0123456789abcdef":
            self.app.set_current_color(key)
            self.app.pop_screen()
        elif key == "escape":
            self.app.pop_screen()
