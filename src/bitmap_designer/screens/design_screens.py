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
        self.viewport_w: int = 0
        self.viewport_h: int = 0
        self.step = self.app.step
        self.scroll_mode = False

    @property
    def undo_stack(self):
        return self.app.history.get_undo(self.app.current_key)

    @property
    def redo_stack(self):
        return self.app.history.get_redo(self.app.current_key)

    # Recalculate viewport dimensions based on available screen space.
    def _recalc_viewport(self):
        self.viewport_w = max(1, (self.size.width - 8) // 2)
        self.viewport_h = max(1, self.size.height - 14)
        self._clamp_offset()

    # Clamp offset so viewport stays within bitmap bounds.
    def _clamp_offset(self):
        self.offset_x = max(0, min(self.offset_x, max(0, self.width - self.viewport_w)))
        self.offset_y = max(0, min(self.offset_y, max(0, self.height - self.viewport_h)))

    @property
    def _content_fits(self) -> bool:
        return self.viewport_w >= self.width and self.viewport_h >= self.height

    # Adjust offset to keep cursor at least 2px from viewport edge.
    def _ensure_cursor_visible(self):
        margin = 2
        if self.viewport_w >= self.width and self.viewport_h >= self.height:
            self.offset_x = 0
            self.offset_y = 0
            return
        if self.cursor_x < self.offset_x + margin:
            self.offset_x = max(0, self.cursor_x - margin)
        elif self.cursor_x >= self.offset_x + self.viewport_w - margin:
            self.offset_x = min(
                max(0, self.width - self.viewport_w),
                self.cursor_x - self.viewport_w + margin + 1
            )
        if self.cursor_y < self.offset_y + margin:
            self.offset_y = max(0, self.cursor_y - margin)
        elif self.cursor_y >= self.offset_y + self.viewport_h - margin:
            self.offset_y = min(
                max(0, self.height - self.viewport_h),
                self.cursor_y - self.viewport_h + margin + 1
            )

    # Shift the viewport by (dx, dy) bitmap pixels. Returns True if offset changed.
    def _scroll(self, dx: int, dy: int) -> bool:
        old_x, old_y = self.offset_x, self.offset_y
        self.offset_x = max(0, min(self.offset_x + dx, max(0, self.width - self.viewport_w)))
        self.offset_y = max(0, min(self.offset_y + dy, max(0, self.height - self.viewport_h)))
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
        self._update_hints()

    def on_screen_resume(self, _event) -> None:
        self.scroll_mode = False
        self.step = self.app.step
        self.query_one("#title", Static).update(self.app.title_with_file(self.base_title))
        if self.app.current_key != self._key_on_enter:
            self._switch_to_key(self.app.current_key)
        self._update_hints()

    # Rebuild the grid display from pixel data.
    def refresh_grid(self):
        self._recalc_viewport()
        vp_w = min(self.viewport_w, self.width - self.offset_x)
        vp_h = min(self.viewport_h, self.height - self.offset_y)

        scrolled_left = self.offset_x > 0
        scrolled_right = self.offset_x + vp_w < self.width
        scrolled_up = self.offset_y > 0
        scrolled_down = self.offset_y + vp_h < self.height

        lines = [" " + self.app.current_key]

        # Top border with scroll indicators
        top = "+"
        if scrolled_left and scrolled_right:
            top += "<"
            top += "-" * max(0, vp_w * 2 - 2)
            top += ">"
        elif scrolled_left:
            top += "<"
            top += "-" * max(0, vp_w * 2 - 1)
        elif scrolled_right:
            top += "-" * max(0, vp_w * 2 - 1)
            top += ">"
        else:
            top += "-" * (vp_w * 2)
        top += "+"
        lines.append(top)

        for i in range(vp_h):
            y = self.offset_y + i
            row = "^" if (scrolled_up and i == 0) else "v" if (scrolled_down and i == vp_h - 1) else "|"
            for j in range(vp_w):
                x = self.offset_x + j
                if x == self.cursor_x and y == self.cursor_y:
                    pixel = self._get_pixel(x, y)
                    if pixel == " ":
                        row += "[reverse]  [/]"
                    else:
                        row += f"[reverse]{pixel}{pixel}[/]"
                else:
                    pixel = self._get_pixel(x, y)
                    row += pixel * 2
            row += "^" if (scrolled_up and i == 0) else "v" if (scrolled_down and i == vp_h - 1) else "|"
            lines.append(row)

        # Bottom border with scroll indicators
        bot = "+"
        if scrolled_left and scrolled_right:
            bot += "<"
            bot += "-" * max(0, vp_w * 2 - 2)
            bot += ">"
        elif scrolled_left:
            bot += "<"
            bot += "-" * max(0, vp_w * 2 - 1)
        elif scrolled_right:
            bot += "-" * max(0, vp_w * 2 - 1)
            bot += ">"
        else:
            bot += "-" * (vp_w * 2)
        bot += "+"
        lines.append(bot)

        grid = "\n".join(lines)
        self.query_one("#grid").update(grid)

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _clear_boundary_status(self):
        if getattr(self, '_last_boundary_msg', False):
            self.query_one("#status", Static).update("")
            self._last_boundary_msg = False

    # Move cursor or scroll by arrow/hjkl keys, applying step and scroll mode.
    def _handle_movement(self, key: str) -> bool:
        BOUNDARY_MSGS = {
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
        step = self.step * (5 if "shift" in mods else 1)

        if self.scroll_mode:
            if base_lower in ("left", "h"):
                if not self._scroll(-step, 0):
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self._clear_boundary_status()
            elif base_lower in ("right", "l"):
                if not self._scroll(step, 0):
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self._clear_boundary_status()
            elif base_lower in ("up", "k"):
                if not self._scroll(0, -step):
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self._clear_boundary_status()
            elif base_lower in ("down", "j"):
                if not self._scroll(0, step):
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self._clear_boundary_status()
        else:
            if base_lower in ("left", "h"):
                new_x = max(0, self.cursor_x - step)
                if new_x == self.cursor_x:
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self.cursor_x = new_x
                    self._clear_boundary_status()
            elif base_lower in ("right", "l"):
                new_x = min(self.width - 1, self.cursor_x + step)
                if new_x == self.cursor_x:
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self.cursor_x = new_x
                    self._clear_boundary_status()
            elif base_lower in ("up", "k"):
                new_y = max(0, self.cursor_y - step)
                if new_y == self.cursor_y:
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self.cursor_y = new_y
                    self._clear_boundary_status()
            elif base_lower in ("down", "j"):
                new_y = min(self.height - 1, self.cursor_y + step)
                if new_y == self.cursor_y:
                    self.show_status(BOUNDARY_MSGS[base_lower])
                    self._last_boundary_msg = True
                else:
                    self.cursor_y = new_y
                    self._clear_boundary_status()
            self._ensure_cursor_visible()

        return True

    def _switch_key_dir(self, direction: str) -> None:
        dest = self.app.navigate_key(direction)
        if dest:
            self._switch_to_key(dest)
        else:
            msgs = {
                "right": "No bitmap key to the right",
                "left": "No bitmap key to the left",
                "down": "No bitmap key below",
                "up": "No bitmap key above",
            }
            self.show_status(msgs[direction])

    def _switch_to_key(self, new_key: str) -> None:
        old_key = self._key_on_enter
        if old_key == new_key:
            return
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
        self._update_hints()
        title = self.query_one("#title", Static)
        title.update(self.app.title_with_file(self.base_title))
        self.show_status(f"Switched to key {new_key}.")

    def on_resize(self) -> None:
        self.refresh_grid()

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return

        key = event.key

        if key == "g":
            if self._content_fits:
                self.show_status("All content visible — scrolling disabled")
                return
            self.scroll_mode = not self.scroll_mode
            if self.scroll_mode:
                self.show_status("Scroll mode on")
            else:
                self.show_status("Scroll mode off")
            self._update_hints()
            return

        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self.step = int(key)
            self.app.step = self.step
            self.show_status(f"Step set to {self.step}")
            self._update_hints()
            return

        k = key.lower()
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
        if k in ("d", "a", "s", "w"):
            dirs = {"d": "right", "a": "left", "s": "down", "w": "up"}
            self._switch_key_dir(dirs[k])
        elif k == "space":
            self.paint_pixel()
        elif k == "f":
            self.flood_fill()
        elif k == "c":
            self.app.push_screen(ColorScreen())
        elif k == "escape":
            if self.scroll_mode:
                self.scroll_mode = False
                self.show_status("Exited scroll mode")
                self._update_hints()
                return
            self.app.pop_screen()
        elif k == "p":
            CodegenService(self.app.bitmaps, self.app.show_status).preview()
        elif k == "m":
            self.app.push_screen(MapScreen())

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
            hints.append("[g] scroll  ", style="dim" if self._content_fits else None)
        hints.append(f"[1-9] Step={self.step}\n")
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
    """Color palette selection screen (0-9, A-F)."""
    CSS = """
    #palette { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file("Select Color"), id="title")
            yield Static(
                "0: transparent  1: black  2: white  3: red  4: yellow\n"
                "5: green  6: cyan  7: magenta  8: orange  9: brown\n"
                "A-F: extended colors",
                id="palette"
            )
            yield Static("[0-9A-F] select  [Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        key = event.key.lower()
        if key in "0123456789abcdef":
            self.app.set_current_color(key)
            self.app.pop_screen()
        elif key == "escape":
            self.app.pop_screen()
