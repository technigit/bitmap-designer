"""Bitmap design and color selection screens."""

from __future__ import annotations
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from .popup_screen import PopupScreen
from ..services.codegen_service import CodegenService
from ..text_utils import columnate

from .bitmap_ops_screen import BitmapOpsScreen
from .help_screen import HelpScreen
from .command_bar import handle_cmd_key
from .config_screen import ConfigKeyScreen, ConfigKeyRenameScreen, ConfigKeyDeleteScreen
from .direction_screen import DirectionSelectScreen, NewKeyScreen
from .map_screen import MapScreen

if TYPE_CHECKING:
    pass


DESIGN_SCROLL_KEY = "\\"


class DesignScreen(Screen):
    """Grid-based bitmap editor with cursor movement, paint, fill, undo/redo."""

    base_title = "Design Mode"
    CSS = """
    #grid { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; margin-left: 3; margin-top: 1; }
    """

    def __init__(self, bitmap_data: dict):
        super().__init__()
        self.width = bitmap_data.get("bounds", {}).get("width", 10)
        self.height = bitmap_data.get("bounds", {}).get("height", 10)
        self.cursor = [0, 0]
        self.cursor_hidden = False
        self.pixels = bitmap_data.get("bitmap", {}).get("pixels", [])
        self._key_on_enter = self.app.current_key
        self._offset = [0, 0]
        self.viewport = [0, 0]
        self.scroll_mode = False
        self.rect_mode = False
        self.rect_start = [0, 0]
        self.cmd_mode = False
        self.cmd_buffer = ""
        self._last_boundary_msg = False
        self._cursor_timer = None
        self._key_level_mode = False
        self._z_pending = False
        self._g_pending = False
        self._y_pending = False
        self._visual_mode = False
        self._visual_start = [0, 0]
        self._clipboard = None
        self._last_action = None
        self._count_pending = 0
        self._d_pending = False
        self._count_for_d = 0

    @property
    def undo_stack(self):
        return self.app.history.get_undo(self.app.current_key)

    @property
    def redo_stack(self):
        return self.app.history.get_redo(self.app.current_key)

    def _recalc_viewport(self):
        self.viewport[0] = max(1, (self.size.width - 8) // 2)
        self.viewport[1] = max(1, self.size.height - 14)
        self._clamp_offset()

    def _clamp_offset(self):
        self._offset[0] = max(
            0, min(self._offset[0], max(0, self.width - self.viewport[0]))
        )
        self._offset[1] = max(
            0, min(self._offset[1], max(0, self.height - self.viewport[1]))
        )

    @property
    def content_fits(self) -> bool:
        return self.viewport[0] >= self.width and self.viewport[1] >= self.height

    def _ensure_cursor_visible(self):
        self.cursor_hidden = False
        margin = 2
        if self.viewport[0] >= self.width and self.viewport[1] >= self.height:
            self._offset[0] = 0
            self._offset[1] = 0
            self.update_hints()
            return
        if self.cursor[0] < self._offset[0] + margin:
            self._offset[0] = max(0, self.cursor[0] - margin)
        elif self.cursor[0] >= self._offset[0] + self.viewport[0] - margin:
            self._offset[0] = min(
                max(0, self.width - self.viewport[0]),
                self.cursor[0] - self.viewport[0] + margin + 1,
            )
        if self.cursor[1] < self._offset[1] + margin:
            self._offset[1] = max(0, self.cursor[1] - margin)
        elif self.cursor[1] >= self._offset[1] + self.viewport[1] - margin:
            self._offset[1] = min(
                max(0, self.height - self.viewport[1]),
                self.cursor[1] - self.viewport[1] + margin + 1,
            )
        self.update_hints()

    def _scroll(self, dx: int, dy: int) -> bool:
        old_x, old_y = self._offset[0], self._offset[1]
        self._offset[0] = max(
            0, min(self._offset[0] + dx, max(0, self.width - self.viewport[0]))
        )
        self._offset[1] = max(
            0, min(self._offset[1] + dy, max(0, self.height - self.viewport[1]))
        )
        return self._offset[0] != old_x or self._offset[1] != old_y

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.base_title), id="title")
        with Vertical():
            yield Static("", id="grid")
            yield Static("", id="hints", markup=False)
        yield Static("", id="status")

    def on_mount(self) -> None:
        ox, oy = self.app.scroll_offsets.get(self.app.current_key, (0, 0))
        self._offset[0], self._offset[1] = ox, oy
        self.refresh_grid()
        self.update_hints()

    def _selection_bounds(self):
        if self.rect_mode:
            return (
                min(self.rect_start[0], self.cursor[0]),
                max(self.rect_start[0], self.cursor[0]),
                min(self.rect_start[1], self.cursor[1]),
                max(self.rect_start[1], self.cursor[1]),
            )
        if self._visual_mode:
            return (
                min(self._visual_start[0], self.cursor[0]),
                max(self._visual_start[0], self.cursor[0]),
                min(self._visual_start[1], self.cursor[1]),
                max(self._visual_start[1], self.cursor[1]),
            )
        return None

    def _in_rect_selection(self, x: int, y: int) -> bool:
        bounds = self._selection_bounds()
        if bounds:
            x1, x2, y1, y2 = bounds
            return x1 <= x <= x2 and y1 <= y <= y2
        return False

    @staticmethod
    def _dim_color(hex_color: str, factor: float = 0.5) -> str:
        if not hex_color or len(hex_color) != 7:
            return hex_color
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"

    def _first_non_blank_col(self, row: int) -> int:
        for col in range(self.width):
            if self._get_pixel(col, row) != " ":
                return col
        return 0

    def _last_non_blank_col(self, row: int) -> int:
        for col in range(self.width - 1, -1, -1):
            if self._get_pixel(col, row) != " ":
                return col
        return 0

    def _cell_markup(
        self, x: int, y: int, *,
        rect_preview: bool = False,
        visual_selection: bool = False,
    ) -> str:
        if rect_preview:
            char = self.app.current_color
        else:
            char = self._get_pixel(x, y)
        color_entry = self.app.active_palette.get(char, {})
        hex_color = color_entry.get("hex", "")
        display_char = color_entry.get("glyph", char) if self.app.glyphmode else char
        cursor = not self.cursor_hidden and x == self.cursor[0] and y == self.cursor[1]

        if char == " ":
            if cursor:
                return "[reverse]  [/]"
            return "  "

        if cursor:
            return f"[reverse]{display_char}{display_char}[/]"

        if visual_selection:
            dimmed = self._dim_color(hex_color)
            if self.app.color_pixels == "on":
                return f"[on {dimmed}]  [/]"
            if self.app.color_pixels == "mixed":
                return f"[{dimmed}]{display_char}{display_char}[/]"
            return f"[dim]{display_char}{display_char}[/]"

        if self.app.color_pixels == "on":
            return f"[on {hex_color}]  [/]"
        if self.app.color_pixels == "mixed":
            return f"[{hex_color}]{display_char}{display_char}[/]"
        return f"{display_char}{display_char}"

    def on_screen_resume(self, _event) -> None:
        self.cursor_hidden = False
        self.scroll_mode = False
        self.rect_mode = False
        self.query_one("#title", Static).update(
            self.app.title_with_file(self.base_title)
        )
        if self.app.current_key != self._key_on_enter:
            self.switch_to_key(self.app.current_key)
        else:
            bm = self.app.bitmaps.get(self.app.current_key, {})
            self.width = bm.get("bounds", {}).get("width", 10)
            self.height = bm.get("bounds", {}).get("height", 10)
            self.pixels = bm.get("bitmap", {}).get("pixels", [])
            self._ensure_cursor_visible()
            self.refresh_grid()
        self.update_hints()
        self._reset_cursor_timer()

    def _reset_cursor_timer(self):
        if self.app.cursor_timeout <= 0:
            return
        if self._cursor_timer is not None:
            self._cursor_timer.stop()
        self._cursor_timer = self.set_timer(
            self.app.cursor_timeout, self._auto_hide_cursor
        )

    def _auto_hide_cursor(self):
        if not self.cursor_hidden:
            self.cursor_hidden = True
            self.refresh_grid()
            self.update_hints()

    def refresh_grid(self):
        self._recalc_viewport()
        vp_w = min(self.viewport[0], self.width - self._offset[0])
        vp_h = min(self.viewport[1], self.height - self._offset[1])

        scrolled_l = self._offset[0] > 0
        scrolled_r = self._offset[0] + vp_w < self.width
        scrolled_u = self._offset[1] > 0
        scrolled_d = self._offset[1] + vp_h < self.height

        lines = [" " + self.app.current_key]
        lines.append(self._border_line(vp_w, scrolled_l, scrolled_r, top=True))
        lines.extend(self._grid_lines(vp_w, vp_h, scrolled_u, scrolled_d))
        lines.append(self._border_line(vp_w, scrolled_l, scrolled_r, top=False))
        self.query_one("#grid").update("\n".join(lines))

    def _border_line(self, vp_w: int, sl: bool, sr: bool, top: bool = True) -> str:
        color = self.app.current_theme.primary or "#00ffff"
        tl, tr = ("╔", "╗") if top else ("╚", "╝")
        h = "═"
        line = f"[{color}]{tl}[/]"
        if sl and sr:
            line += f"[white]<[/][{color}]{h * max(0, vp_w * 2 - 2)}[/][white]>[/]"
        elif sl:
            line += f"[white]<[/][{color}]{h * max(0, vp_w * 2 - 1)}[/]"
        elif sr:
            line += f"[{color}]{h * max(0, vp_w * 2 - 1)}[/][white]>[/]"
        else:
            line += f"[{color}]{h * vp_w * 2}[/]"
        line += f"[{color}]{tr}[/]"
        return line

    def _grid_lines(self, vp_w: int, vp_h: int, su: bool, sd: bool) -> list[str]:
        color = self.app.current_theme.primary or "#00ffff"
        rows = []
        for i in range(vp_h):
            y = self._offset[1] + i
            ind_char = (
                "^" if (su and i == 0) else "v" if (sd and i == vp_h - 1) else "║"
            )
            ind_style = "white" if ind_char in ("^", "v") else color
            row = f"[{ind_style}]{ind_char}[/]"
            for j in range(vp_w):
                x = self._offset[0] + j
                in_rect = self.rect_mode and self._in_rect_selection(x, y)
                in_visual = self._visual_mode and self._in_rect_selection(x, y) and not in_rect
                row += self._cell_markup(
                    x, y, rect_preview=in_rect, visual_selection=in_visual
                )
            row += f"[{ind_style}]{ind_char}[/]"
            rows.append(row)
        return rows

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _clear_boundary_status(self):
        if self._last_boundary_msg:
            self.query_one("#status", Static).update("")
            self._last_boundary_msg = False

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
        base_lower = parts[-1].lower()

        if base_lower not in ("left", "right", "up", "down", "h", "j", "k", "l"):
            return False

        if self.scroll_mode:
            self._scroll_move(base_lower, boundary_msgs)
        else:
            self._cursor_move(base_lower, boundary_msgs)
            self._ensure_cursor_visible()

        return True

    def _scroll_move(self, base_lower: str, msgs: dict) -> None:
        deltas = {
            "left": (-1, 0),
            "h": (-1, 0),
            "right": (1, 0),
            "l": (1, 0),
            "up": (0, -1),
            "k": (0, -1),
            "down": (0, 1),
            "j": (0, 1),
        }
        dx, dy = deltas[base_lower]
        if not self._scroll(dx, dy):
            self.show_status(msgs[base_lower])
            self._last_boundary_msg = True
        else:
            self._clear_boundary_status()

    def _cursor_move(self, base_lower: str, msgs: dict) -> None:
        if self.cursor_hidden:
            self.cursor_hidden = False
        if base_lower in ("left", "h"):
            nx = max(0, self.cursor[0] - 1)
            if nx == self.cursor[0]:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor[0] = nx
        elif base_lower in ("right", "l"):
            nx = min(self.width - 1, self.cursor[0] + 1)
            if nx == self.cursor[0]:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor[0] = nx
        elif base_lower in ("up", "k"):
            ny = max(0, self.cursor[1] - 1)
            if ny == self.cursor[1]:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor[1] = ny
        elif base_lower in ("down", "j"):
            ny = min(self.height - 1, self.cursor[1] + 1)
            if ny == self.cursor[1]:
                self.show_status(msgs[base_lower])
                self._last_boundary_msg = True
                return
            self.cursor[1] = ny
        self._reset_cursor_timer()
        self._clear_boundary_status()

    def on_resize(self) -> None:
        self.refresh_grid()

    def _on_key_rect_mode(self, key: str) -> None:
        k_low = key.lower()
        if self.cursor_hidden:
            self.cursor_hidden = False
        if k_low in ("left", "right", "up", "down", "h", "j", "k", "l"):
            parts = key.split("+")
            base = parts[-1]
            base_low = base.lower()
            if base_low in ("left", "h"):
                self.cursor[0] = max(0, self.cursor[0] - 1)
            elif base_low in ("right", "l"):
                self.cursor[0] = min(self.width - 1, self.cursor[0] + 1)
            elif base_low in ("up", "k"):
                self.cursor[1] = max(0, self.cursor[1] - 1)
            elif base_low in ("down", "j"):
                self.cursor[1] = min(self.height - 1, self.cursor[1] + 1)
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return
        if k_low in ("enter", "\n"):
            self._paint_rectangle()
            self.rect_mode = False
            self.show_status("Rectangle painted")
            self.update_hints()
            self.refresh_grid()
            return
        if k_low == "escape":
            self.cursor[0] = self.rect_start[0]
            self.cursor[1] = self.rect_start[1]
            self.rect_mode = False
            self.show_status("Rectangle cancelled")
            self.update_hints()
            self.refresh_grid()
            return

    def on_key(self, event) -> None:  # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
        key = event.key

        if handle_cmd_key(self, event):
            event.stop()
            return

        if self._z_pending:
            self._z_pending = False
            if key == "escape":
                self.show_status("")
                return
            if key in ("l", "h", "L", "H"):
                dx = 1 if key.islower() else max(1, self.viewport[0] // 2)
                factor = -1 if key.lower() == "h" else 1
                self._offset[0] = max(
                    0, min(self._offset[0] + factor * dx, max(0, self.width - self.viewport[0]))
                )
                self.cursor[0] = max(0, min(self.width - 1, self.cursor[0] + factor * dx))
                self.cursor_hidden = False
                self.refresh_grid()
                return
            return

        if self._g_pending:
            self._g_pending = False
            if key == "g":
                self._goto_first()
                self.refresh_grid()
                return
            if key == "escape":
                self.show_status("")
                return
            ch = getattr(event, "character", None)
            if ch == "^":
                limit = min(self._offset[0] + self.viewport[0], self.width)
                for col in range(self._offset[0], limit):
                    if self._get_pixel(col, self.cursor[1]) != " ":
                        self.cursor[0] = col
                        break
                else:
                    self.cursor[0] = self._offset[0]
            elif ch == "$":
                limit = min(self._offset[0] + self.viewport[0], self.width) - 1
                for col in range(limit, self._offset[0] - 1, -1):
                    if self._get_pixel(col, self.cursor[1]) != " ":
                        self.cursor[0] = col
                        break
                else:
                    self.cursor[0] = limit
            else:
                return
            self.cursor_hidden = False
            self.update_hints()
            self.refresh_grid()
            return

        if self._y_pending:
            self._y_pending = False
            if key == "y":
                self._yank_line()
                self.refresh_grid()
                return
            if key == "escape":
                self.show_status("")
                return

        if self._d_pending:
            self._d_pending = False
            if key == "d":
                self._delete_lines(self._count_for_d or 1)
                self._count_for_d = 0
                self.refresh_grid()
                return
            if key == "escape":
                self.show_status("")
                return
            self.show_status("")

        if key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return

        if key in ("ctrl+u", "ctrl+d"):
            dy = max(1, self.viewport[1] // 2)
            factor = -1 if key == "ctrl+u" else 1
            self._offset[1] = max(
                0, min(self._offset[1] + factor * dy, max(0, self.height - self.viewport[1]))
            )
            self.cursor[1] = max(0, min(self.height - 1, self.cursor[1] + factor * dy))
            self.refresh_grid()
            self._reset_cursor_timer()
            return

        if key == "tab":
            self._toggle_cursor_hidden()
            return

        if key in (DESIGN_SCROLL_KEY, "backslash"):
            if self.content_fits:
                self.show_status("All content visible — scrolling disabled")
                return
            self.scroll_mode = not self.scroll_mode
            self.show_status(
                "Scroll mode on" if self.scroll_mode else "Scroll mode off"
            )
            self.update_hints()
            return

        if key in ("`", "grave_accent"):
            self._key_level_mode = not self._key_level_mode
            mode = "key" if self._key_level_mode else "bitmap"
            self.show_status(f"Switched to {mode} mode")
            self.update_hints()
            return

        if self.rect_mode:
            self._on_key_rect_mode(key)
            return

        if self._visual_mode:
            self._on_key_visual(key)
            return

        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._count_pending = self._count_pending * 10 + int(key)
            self.show_status(str(self._count_pending))
            return

        if self._count_pending > 0:
            count = self._count_pending
            self._count_pending = 0
            if key == "G":
                y = min(max(0, count - 1), self.height - 1)
                self.cursor = [self._first_non_blank_col(y), y]
                if not self._key_level_mode:
                    self.show_status(f"Line {y + 1} of {self.height}")
                self._ensure_cursor_visible()
                self._reset_cursor_timer()
                self.refresh_grid()
                return
            if key == "x":
                self._delete_chars(count)
                self.refresh_grid()
                return
            if key == "space":
                self._save_state()
                for _ in range(count):
                    self._paint_pixel_no_save()
                self._sync_pixels()
                self.app.mark_dirty()
                CodegenService(
                    self.app.bitmaps, palette=self.app.active_palette
                ).save_preview_html()
                self._store_last_action(
                    {"type": "paint", "color": self.app.current_color}
                )
                self.show_status(f"Painted {count} pixels")
                self.refresh_grid()
                return
            if key in ("h", "j", "k", "l", "left", "right", "up", "down"):
                dirs = {
                    "h": (-count, 0),
                    "j": (0, count),
                    "k": (0, -count),
                    "l": (count, 0),
                    "left": (-count, 0),
                    "right": (count, 0),
                    "up": (0, -count),
                    "down": (0, count),
                }
                dx, dy = dirs[key]
                self.cursor[0] = max(0, min(self.width - 1, self.cursor[0] + dx))
                self.cursor[1] = max(0, min(self.height - 1, self.cursor[1] + dy))
                self._ensure_cursor_visible()
                self._reset_cursor_timer()
                self.refresh_grid()
                return
            if key == "D":
                self._delete_lines(count)
                self.refresh_grid()
                return
            if key == "p":
                if not self._clipboard:
                    self.show_status("Nothing to paste")
                    return
                self._save_state()
                for _ in range(count):
                    self._paste_clipboard_at_cursor()
                    self._advance_paste_cursor()
                self._sync_pixels()
                self.app.mark_dirty()
                CodegenService(
                    self.app.bitmaps, palette=self.app.active_palette
                ).save_preview_html()
                self._store_last_action({"type": "paste"})
                self.show_status(f"Pasted {count} times")
                self.refresh_grid()
                return
            if key == ".":
                if not self._last_action:
                    self.show_status("No previous action to repeat")
                    return
                self._save_state()
                for _ in range(count):
                    self._execute_action(self._last_action)
                self._sync_pixels()
                self.app.mark_dirty()
                CodegenService(
                    self.app.bitmaps, palette=self.app.active_palette
                ).save_preview_html()
                self._store_last_action(dict(self._last_action))
                self.show_status(f"Repeated {count} times")
                self.refresh_grid()
                return
            if key == "d":
                self._count_for_d = count
                self._d_pending = True
                self.show_status("d")
                return
            if key == "escape":
                self.show_status("")
                return

        if key == "d" and not self._key_level_mode:
            self._d_pending = True
            self.show_status("d")
            return

        if key == "z":
            self._z_pending = True
            self.show_status("z")
            return

        if key == "g":
            self._g_pending = True
            self.show_status("g")
            return

        if key == "y" and not self._visual_mode:
            self._y_pending = True
            self.show_status("y")
            return

        if key == "O":
            self.app.push_screen(BitmapOpsScreen(), self._on_bitmap_ops_result)
            return

        if key == "b":
            if self._key_level_mode:
                self.app.push_screen(BitmapOpsScreen(), self._on_bitmap_ops_result)
            else:
                self._prev_color_word()
                self.refresh_grid()
            return

        if key == "W" and not self._key_level_mode:
            self._next_vertical_color_run()
            self.refresh_grid()
            return

        if key == "B" and not self._key_level_mode:
            self._prev_vertical_color_run()
            self.refresh_grid()
            return

        ch = getattr(event, "character", None)
        if ch == "^":
            if self._key_level_mode:
                self._goto_first_key()
            else:
                self.cursor[0] = self._first_non_blank_col(self.cursor[1])
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return

        if ch == "$":
            if self._key_level_mode:
                self._goto_last_key()
            else:
                self.cursor[0] = self._last_non_blank_col(self.cursor[1])
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return

        if key == "0":
            if self._key_level_mode:
                self._goto_first_key()
            else:
                self.cursor[0] = 0
                self.show_status(f"Column 1 of {self.width}")
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return

        if key == "G":
            if self._key_level_mode:
                self._goto_last_key()
            else:
                y = self.height - 1
                self.cursor = [self._first_non_blank_col(y), y]
                self.show_status(f"Line {y + 1} of {self.height}")
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return

        if key in ("enter", "\n"):
            self.cursor[0] = 0
            self.cursor[1] = min(self.cursor[1] + 1, self.height - 1)
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return

        if key == "e":
            self._eyedropper()
            self.refresh_grid()
            return

        if key == "v":
            self._start_visual_mode()
            return

        if key == "p":
            self._paste()
            self.refresh_grid()
            return

        if key == "P":
            svc = CodegenService(
                self.app.bitmaps,
                self.app.show_status,
                palette=self.app.active_palette,
            )
            svc.preview()
            return

        if key == "D":
            self._delete_lines(1)
            self.refresh_grid()
            return

        if key == "x":
            self._delete_chars(1)
            self.refresh_grid()
            return

        if key == ".":
            self._repeat_last_action()
            self.refresh_grid()
            return

        if key == "?" or getattr(event, "character", None) == "?":
            self.app.push_screen(HelpScreen(mode="design"))
            return

        self._on_key_action(key, event)

    def _on_key_visual(self, key: str) -> None:
        k_low = key.lower()
        if k_low in ("left", "right", "up", "down", "h", "j", "k", "l"):
            parts = key.split("+")
            base = parts[-1]
            base_low = base.lower()
            if base_low in ("left", "h"):
                self.cursor[0] = max(0, self.cursor[0] - 1)
            elif base_low in ("right", "l"):
                self.cursor[0] = min(self.width - 1, self.cursor[0] + 1)
            elif base_low in ("up", "k"):
                self.cursor[1] = max(0, self.cursor[1] - 1)
            elif base_low in ("down", "j"):
                self.cursor[1] = min(self.height - 1, self.cursor[1] + 1)
            self._ensure_cursor_visible()
            self.refresh_grid()
            self._reset_cursor_timer()
            return
        if k_low == "y":
            self._yank_visual_selection()
            self._visual_mode = False
            self.show_status("Selection yanked")
            self.update_hints()
            self.refresh_grid()
            return
        if k_low == "escape":
            self._visual_mode = False
            self.show_status("Visual mode cancelled")
            self.update_hints()
            self.refresh_grid()
            return

    def _toggle_cursor_hidden(self) -> None:
        self.cursor_hidden = not self.cursor_hidden
        if self.cursor_hidden:
            if self._cursor_timer is not None:
                self._cursor_timer.stop()
                self._cursor_timer = None
        else:
            self._reset_cursor_timer()
        self.show_status("Cursor hidden" if self.cursor_hidden else "Cursor visible")
        self.update_hints()
        self.refresh_grid()
        self.update_hints()

    def _on_bitmap_ops_result(self, result: str | None) -> None:
        if result == "n":
            self.app.push_screen(
                DirectionSelectScreen(), self._on_new_key_direction
            )
        elif result == "c":
            self.app.push_screen(
                DirectionSelectScreen(), self._on_dup_key_direction
            )
        elif result == "r":
            self.app.push_screen(ConfigKeyRenameScreen())
        elif result == "d":
            self.app.push_screen(ConfigKeyDeleteScreen())

    def _on_new_key_direction(self, direction: str | None) -> None:
        if direction:
            self.app.push_screen(
                NewKeyScreen(
                    direction,
                    False,
                    self.app.next_key_name(),
                    self.app.current_key,
                )
            )

    def _on_dup_key_direction(self, direction: str | None) -> None:
        if direction:
            self.app.push_screen(
                NewKeyScreen(
                    direction,
                    True,
                    self.app.next_key_name(),
                    self.app.current_key,
                )
            )

    def _switch_key_dir(self, direction: str) -> None:
        dest = self.app.navigate_key(direction)
        if dest:
            self.switch_to_key(dest)
            return
        keys = list(self.app.bitmaps.keys())
        if len(keys) <= 1:
            return
        current = self.app.bitmaps[self.app.current_key]
        cx = current.get("location", {}).get("x", 0)
        cy = current.get("location", {}).get("y", 0)
        if direction in ("right", "left"):
            same = [
                k
                for k in keys
                if k != self.app.current_key
                and self.app.bitmaps[k].get("location", {}).get("y", 0) == cy
            ]
            if not same:
                same = [k for k in keys if k != self.app.current_key]
            if direction == "right":
                dest = min(
                    same,
                    key=lambda k: self.app.bitmaps[k]
                    .get("location", {})
                    .get("x", 0),
                )
            else:
                dest = max(
                    same,
                    key=lambda k: self.app.bitmaps[k]
                    .get("location", {})
                    .get("x", 0),
                )
        else:
            same = [
                k
                for k in keys
                if k != self.app.current_key
                and self.app.bitmaps[k].get("location", {}).get("x", 0) == cx
            ]
            if not same:
                same = [k for k in keys if k != self.app.current_key]
            if direction == "down":
                dest = min(
                    same,
                    key=lambda k: self.app.bitmaps[k]
                    .get("location", {})
                    .get("y", 0),
                )
            else:
                dest = max(
                    same,
                    key=lambda k: self.app.bitmaps[k]
                    .get("location", {})
                    .get("y", 0),
                )
        if dest:
            self.switch_to_key(dest)

    def switch_to_key(self, new_key: str) -> None:
        old_key = self._key_on_enter
        if old_key == new_key:
            return
        self.cursor_hidden = False
        self.rect_mode = False
        self.app.cursor_positions[old_key] = (self.cursor[0], self.cursor[1])
        self.app.scroll_offsets[old_key] = (self._offset[0], self._offset[1])
        self.app.set_current_key(new_key)
        self._key_on_enter = new_key
        bm = self.app.bitmaps.get(new_key, {})
        self.width = bm.get("bounds", {}).get("width", 10)
        self.height = bm.get("bounds", {}).get("height", 10)
        self.pixels = bm.get("bitmap", {}).get("pixels", [])
        cx, cy = self.app.cursor_positions.get(new_key, (0, 0))
        self.cursor[0] = min(cx, self.width - 1)
        self.cursor[1] = min(cy, self.height - 1)
        ox, oy = self.app.scroll_offsets.get(new_key, (0, 0))
        self._offset[0], self._offset[1] = ox, oy
        self.refresh_grid()
        self.update_hints()
        title = self.query_one("#title", Static)
        title.update(self.app.title_with_file(self.base_title))
        self.show_status(f"Switched to key {new_key}.")

    def _on_key_action(self, k: str, event) -> None:
        if k == "u":
            self._undo()
            return
        if k == "ctrl+r":
            self._redo()
            return
        if k in ("H", "M", "L"):
            if k == "H":
                row = self._offset[1]
            elif k == "M":
                row = self._offset[1] + self.viewport[1] // 2
            else:
                row = min(self._offset[1] + self.viewport[1], self.height) - 1
            self.cursor = [self._first_non_blank_col(row), row]
            self.cursor_hidden = False
            self.update_hints()
            self.refresh_grid()
            return
        if k in ("J", "K"):
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
            if not self._key_level_mode:
                if k == "w":
                    self._next_color_word()
                return
            dirs = {"d": "right", "a": "left", "s": "down", "w": "up"}
            self._switch_key_dir(dirs[k])
        elif k == "space":
            self.paint_pixel()
        elif k == "f":
            self.flood_fill()
        elif k == "r":
            self.rect_mode = True
            self.rect_start[0] = self.cursor[0]
            self.rect_start[1] = self.cursor[1]
            self.update_hints()
            self.show_status("Rectangle mode")
            self.refresh_grid()
            self._reset_cursor_timer()
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
        elif k == "m":
            self.app.push_screen(MapScreen())

        self.refresh_grid()

    def paint_pixel(self):
        new_color = " " if self.app.current_color == "0" else self.app.current_color
        if self._get_pixel(self.cursor[0], self.cursor[1]) == new_color:
            return
        self._save_state()
        self._paint_pixel_no_save()
        self._sync_pixels()
        self.app.mark_dirty()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self._store_last_action(
            {"type": "paint", "color": self.app.current_color}
        )

    def flood_fill(self):
        self._save_state()
        target = self._get_pixel(self.cursor[0], self.cursor[1])
        fill_color = self.app.current_color
        if target == fill_color:
            return
        self._flood_fill(self.cursor[0], self.cursor[1], target, fill_color)
        self.app.mark_dirty()
        self._sync_pixels()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self._store_last_action({"type": "fill", "color": fill_color})

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
        x1 = min(self.rect_start[0], self.cursor[0])
        x2 = max(self.rect_start[0], self.cursor[0])
        y1 = min(self.rect_start[1], self.cursor[1])
        y2 = max(self.rect_start[1], self.cursor[1])
        fill = self.app.current_color
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self._set_pixel(x, y, fill)
        self.app.mark_dirty()
        self._sync_pixels()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self._store_last_action(
            {
                "type": "rect",
                "color": fill,
                "width": x2 - x1 + 1,
                "height": y2 - y1 + 1,
            }
        )

    def _save_state(self):
        self.undo_stack.append((list(self.pixels), self.cursor[0], self.cursor[1]))
        self.redo_stack.clear()
        self.update_hints()

    def _sync_pixels(self) -> None:
        key = self.app.current_key
        if key in self.app.bitmaps:
            self.app.bitmaps[key].setdefault("bitmap", {})["pixels"] = list(self.pixels)
            self.app.mark_dirty()

    def _undo(self):
        if not self.undo_stack:
            self.show_status("Already at oldest change")
            return
        if len(self.undo_stack[-1]) != 3:
            self.undo_stack.pop()
            return
        _, saved_cx, saved_cy = self.undo_stack[-1]
        self.redo_stack.append((list(self.pixels), saved_cx, saved_cy))
        self.pixels, self.cursor[0], self.cursor[1] = self.undo_stack.pop()
        self.cursor_hidden = False
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
        if len(self.redo_stack[-1]) != 3:
            self.redo_stack.pop()
            return
        _, saved_cx, saved_cy = self.redo_stack[-1]
        self.undo_stack.append((list(self.pixels), saved_cx, saved_cy))
        self.pixels, self.cursor[0], self.cursor[1] = self.redo_stack.pop()
        self.cursor_hidden = False
        self._sync_pixels()
        self.app.mark_dirty()
        self.update_hints()
        self.refresh_grid()
        total = len(self.undo_stack) + len(self.redo_stack)
        self.show_status(f"After change #{len(self.undo_stack)} of {total}")

    def update_hints(self):
        hints = Text()
        if self.rect_mode:
            hints.append("[hjkl/\u25b4\u25be\u25c2\u25b8] select opposite corner  ")
            hints.append("[Enter] confirm  [Escape] cancel")
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
                hints.append("[⌃R]edo", style="dim")
            else:
                hints.append("[⌃R]edo")
            hints.append("\n")
            if self.scroll_mode:
                hints.append(
                    "[hjkl/\u25b4\u25be\u25c2\u25b8] scroll  [Escape] exit scroll  "
                )
            else:
                hints.append("[hjkl/\u25b4\u25be\u25c2\u25b8] move  ")
                hints.append(
                    "[\\] scroll  ", style="dim" if self.content_fits else None
                )
            hints.append("[?] help\n")
            if self._key_level_mode:
                if len(self.app.bitmaps) <= 1:
                    hints.append("[wasd] switch key  ", style="dim")
                else:
                    hints.append("[wasd] switch key  ")
            else:
                w_style = "dim" if not self._has_next_color_word() else None
                hints.append("[w\u2192] ", style=w_style)
                cap_w_style = "dim" if not self._has_next_vertical_color_run() else None
                hints.append("[W\u2193] ", style=cap_w_style)
                b_style = "dim" if not self._has_prev_color_word() else None
                hints.append("[b\u2190] ", style=b_style)
                cap_b_style = "dim" if not self._has_prev_vertical_color_run() else None
                hints.append("[B\u2191] ", style=cap_b_style)
                hints.append("color run  ")
            hints.append("[/] find key  ")
            mode_str = "key" if self._key_level_mode else "bitmap"
            hints.append(f"[`] {mode_str}\n")
            hints.append("[⇧O]ps  ")
            hints.append("[M]ap  ")
            hints.append("[⇧P]review  ")
            hints.append(f"[Tab] {'show' if self.cursor_hidden else 'hide'} cursor  ")
            hints.append("[Escape] back")
        self.query_one("#hints", Static).update(hints)

    def _eyedropper(self) -> None:
        color = self._get_pixel(self.cursor[0], self.cursor[1])
        if color == " ":
            self.show_status("Empty pixel — color not changed")
            return
        self.app.set_current_color(color)
        self.show_status(f"Color set to {color}")

    def _next_color_word(self) -> None:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        x = self.cursor[0] + 1
        while x < self.width:
            if self._get_pixel(x, self.cursor[1]) != current_color:
                self.cursor[0] = x
                self._ensure_cursor_visible()
                self._reset_cursor_timer()
                self.refresh_grid()
                return
            x += 1
        self.show_status("No more color changes on this line")

    def _prev_color_word(self) -> None:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        x = self.cursor[0] - 1
        while x >= 0:
            if self._get_pixel(x, self.cursor[1]) != current_color:
                self.cursor[0] = x
                self._ensure_cursor_visible()
                self._reset_cursor_timer()
                return
            x -= 1
        self.show_status("No more color changes on this line")

    def _next_vertical_color_run(self) -> None:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        y = self.cursor[1] + 1
        while y < self.height:
            if self._get_pixel(self.cursor[0], y) != current_color:
                self.cursor[1] = y
                self._ensure_cursor_visible()
                self._reset_cursor_timer()
                self.show_status(
                    f"Run {y + 1} of {self.height} in column {self.cursor[0]}"
                )
                return
            y += 1
        self.show_status("No more color runs in this column")

    def _prev_vertical_color_run(self) -> None:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        y = self.cursor[1] - 1
        while y >= 0:
            if self._get_pixel(self.cursor[0], y) != current_color:
                self.cursor[1] = y
                self._ensure_cursor_visible()
                self._reset_cursor_timer()
                self.show_status(
                    f"Run {y + 1} of {self.height} in column {self.cursor[0]}"
                )
                return
            y -= 1
        self.show_status("No more color runs in this column")

    def _has_next_color_word(self) -> bool:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        for x in range(self.cursor[0] + 1, self.width):
            if self._get_pixel(x, self.cursor[1]) != current_color:
                return True
        return False

    def _has_prev_color_word(self) -> bool:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        for x in range(self.cursor[0] - 1, -1, -1):
            if self._get_pixel(x, self.cursor[1]) != current_color:
                return True
        return False

    def _has_next_vertical_color_run(self) -> bool:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        for y in range(self.cursor[1] + 1, self.height):
            if self._get_pixel(self.cursor[0], y) != current_color:
                return True
        return False

    def _has_prev_vertical_color_run(self) -> bool:
        current_color = self._get_pixel(self.cursor[0], self.cursor[1])
        for y in range(self.cursor[1] - 1, -1, -1):
            if self._get_pixel(self.cursor[0], y) != current_color:
                return True
        return False

    def _start_visual_mode(self) -> None:
        self._visual_mode = True
        self._visual_start[0] = self.cursor[0]
        self._visual_start[1] = self.cursor[1]
        self.show_status("Visual mode — move cursor to expand selection")
        self.update_hints()
        self.refresh_grid()

    def _yank_visual_selection(self) -> None:
        x1 = min(self._visual_start[0], self.cursor[0])
        x2 = max(self._visual_start[0], self.cursor[0])
        y1 = min(self._visual_start[1], self.cursor[1])
        y2 = max(self._visual_start[1], self.cursor[1])
        data = []
        for y in range(y1, y2 + 1):
            row = []
            for x in range(x1, x2 + 1):
                row.append(self._get_pixel(x, y))
            data.append(row)
        self._clipboard = data
        self.show_status(
            f"Yanked {x2 - x1 + 1}x{y2 - y1 + 1} block"
        )

    def _yank_line(self) -> None:
        y = self.cursor[1]
        row = []
        for x in range(self.width):
            row.append(self._get_pixel(x, y))
        self._clipboard = [row]
        self.show_status(f"Yanked line {y + 1}")

    def _paste(self) -> None:
        if not self._clipboard:
            self.show_status("Nothing to paste")
            return
        self._save_state()
        self._paste_clipboard_at_cursor()
        self._advance_paste_cursor()
        self._sync_pixels()
        self.app.mark_dirty()
        self._store_last_action({"type": "paste"})
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self.show_status(
            f"Pasted {len(self._clipboard[0])}x{len(self._clipboard)} block"
        )
        self.refresh_grid()

    def _store_last_action(self, action: dict) -> None:
        self._last_action = action

    def _repeat_last_action(self) -> None:
        if not self._last_action:
            self.show_status("No previous action to repeat")
            return
        action = self._last_action
        self._save_state()
        self._execute_action(action)
        self._sync_pixels()
        self.app.mark_dirty()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self._store_last_action(dict(action))

    def _repaint_rect(self, action: dict) -> None:
        w = action.get("width", 1)
        h = action.get("height", 1)
        color = action.get("color", self.app.current_color)
        self._save_state()
        for dy in range(h):
            for dx in range(w):
                x = self.cursor[0] + dx
                y = self.cursor[1] + dy
                if 0 <= x < self.width and 0 <= y < self.height:
                    self._set_pixel(x, y, color)
        self._sync_pixels()
        self.app.mark_dirty()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()

    def _delete_chars(self, count: int) -> None:
        self._save_state()
        deleted = 0
        for i in range(count):
            x = self.cursor[0] + i
            if x >= self.width:
                break
            self._set_pixel(x, self.cursor[1], " ")
            deleted += 1
        self._sync_pixels()
        self.app.mark_dirty()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self._store_last_action({"type": "paint", "color": "0"})
        self.show_status(f"Deleted {deleted} pixel{'s' if deleted != 1 else ''}")

    def _paint_pixel_no_save(self) -> None:
        color = " " if self.app.current_color == "0" else self.app.current_color
        if len(self.pixels) <= self.cursor[1]:
            self.pixels.extend(
                [" " * self.width for _ in range(self.cursor[1] - len(self.pixels) + 1)]
            )
        row = list(self.pixels[self.cursor[1]])
        if len(row) <= self.cursor[0]:
            row.extend([" "] * (self.cursor[0] - len(row) + 1))
        row[self.cursor[0]] = color
        self.pixels[self.cursor[1]] = "".join(row)
        self.cursor[0] += 1
        if self.cursor[0] >= self.width:
            self.cursor[0] = 0
            self.cursor[1] = min(self.cursor[1] + 1, self.height - 1)

    def _paste_clipboard_at_cursor(self) -> None:
        for dy, row in enumerate(self._clipboard):
            for dx, char in enumerate(row):
                x = self.cursor[0] + dx
                y = self.cursor[1] + dy
                if 0 <= x < self.width and 0 <= y < self.height:
                    self._set_pixel(x, y, char)

    def _advance_paste_cursor(self) -> None:
        if self._clipboard:
            w = len(self._clipboard[0])
            self.cursor[0] += w
            if self.cursor[0] >= self.width:
                self.cursor[0] = 0
                self.cursor[1] = min(self.cursor[1] + 1, self.height - 1)

    def _execute_action(self, action: dict) -> None:
        t = action["type"]
        if t == "paint":
            saved_color = self.app.current_color
            self.app.set_current_color(action.get("color", saved_color))
            self._paint_pixel_no_save()
            self.app.set_current_color(saved_color)
        elif t == "fill":
            target = self._get_pixel(self.cursor[0], self.cursor[1])
            fill_color = action.get("color", self.app.current_color)
            if target != fill_color:
                self._flood_fill(self.cursor[0], self.cursor[1], target, fill_color)
        elif t == "rect":
            w = action.get("width", 1)
            h = action.get("height", 1)
            color = action.get("color", self.app.current_color)
            for dy in range(h):
                for dx in range(w):
                    x = self.cursor[0] + dx
                    y = self.cursor[1] + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self._set_pixel(x, y, color)
        elif t == "paste":
            self._paste_clipboard_at_cursor()
            self._advance_paste_cursor()

    def _delete_lines(self, n: int) -> None:
        self._save_state()
        end_y = min(self.cursor[1] + n, self.height)
        deleted = 0
        for y in range(self.cursor[1], end_y):
            for x in range(self.width):
                self._set_pixel(x, y, " ")
            deleted += 1
        self._sync_pixels()
        self.app.mark_dirty()
        CodegenService(
            self.app.bitmaps, palette=self.app.active_palette
        ).save_preview_html()
        self._store_last_action(
            {"type": "rect", "color": "0", "width": self.width, "height": deleted}
        )
        self.show_status(f"Deleted {deleted} line{'s' if deleted != 1 else ''}")

    def _goto_first(self) -> None:
        if self._key_level_mode:
            self._goto_first_key()
        else:
            self.cursor = [self._first_non_blank_col(0), 0]
        self._ensure_cursor_visible()
        self._reset_cursor_timer()
        self.refresh_grid()
        self.show_status("")

    def _goto_first_key(self) -> None:
        if not self.app.bitmaps:
            return
        first = next(iter(self.app.bitmaps.keys()))
        self.switch_to_key(first)

    def _goto_last_key(self) -> None:
        if not self.app.bitmaps:
            return
        last = list(self.app.bitmaps.keys())[-1]
        self.switch_to_key(last)


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
            rows.append(
                (
                    f"{asterisk}{cid.upper()}:",
                    name,
                    f"({glyph_display})",
                    f"[{hex_color}]{cid.upper()}[/]",
                )
            )
        self.query_one("#palette", Static).update(columnate(rows, sep="  "))

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
