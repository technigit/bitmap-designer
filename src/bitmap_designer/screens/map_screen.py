"""Spatial overview screen showing all bitmap keys on a virtual canvas."""

from __future__ import annotations
import copy
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Resize as ResizeEvent
from textual.screen import Screen
from textual.widgets import Input, Static
from textual.containers import Vertical

from .bitmap_ops_screen import BitmapOpsScreen
from .help_screen import HelpScreen, MAP_PAGE_ACTION, MAP_PAGE_GHOST, MAP_PAGE_ZOOM
from .command_bar import handle_cmd_key
from .config_screen import ConfigKeyDeleteScreen, ConfigKeyRenameScreen
from .popup_screen import PopupScreen
from ..constants import create_default_bitmap
from .direction_screen import DirectionSelectScreen, NewKeyScreen

if TYPE_CHECKING:
    pass


@dataclass
class DeviceContext:
    """Render-time state snapshot: canvas dimensions, zoom, pan, aspect."""

    cw: int
    ch: int
    zoom_scale: float
    aspect_y: float
    pan_x: int
    pan_y: int


class FindKeyScreen(PopupScreen):
    """Screen to find and select a bitmap key by name."""

    base_title = "Find Key"
    CSS = """
    Input { margin: 0 0; }
    #matches { margin-top: 1; }
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            self.input = Input(
                value=self.app.current_key,
                placeholder="Type key name...",
                id="find-input",
            )
            yield self.input
            yield Static("", id="matches")
            yield Static(
                "[Enter] select/create  [Escape] cancel", id="hints", markup=False
            )
            yield Static("", id="status")

    def on_screen_resume(self, _event) -> None:
        self.input.value = self.app.current_key
        self.input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        val = event.value.strip()
        if val:
            keys = [k for k in self.app.bitmaps if val.lower() in k.lower()]
            display = "\n".join(keys[:15])
            self.query_one("#matches", Static).update(display)
        else:
            self.query_one("#matches", Static).update("")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.dismiss(None)
        elif event.key in ("enter", "\n"):
            val = (self.input.value or "").strip()
            if val and " " not in val:
                is_new = val not in self.app.bitmaps
                if is_new:
                    bm = create_default_bitmap()
                    bm["location"] = self.app.find_empty_location()
                    self.app.bitmaps[val] = bm
                    self.app.build_key_adjacency()
                    self.app.mark_dirty()
                self.dismiss((val, is_new))
            else:
                self.show_status("Please enter a valid key (no spaces).")


PAN_KEYS = {
    "left": (-1, 0),
    "h": (-1, 0),
    "right": (1, 0),
    "l": (1, 0),
    "up": (0, -1),
    "k": (0, -1),
    "down": (0, 1),
    "j": (0, 1),
}

GHOST_MOVE_KEYS = {
    **PAN_KEYS,
    "w": (0, -1),
    "a": (-1, 0),
    "s": (0, 1),
    "d": (1, 0),
    " ": (1, 0),
    "space": (1, 0),
}


class MapScreen(Screen):
    """Overview map of all bitmaps arranged by spatial location."""

    base_title = "Map Mode"
    CSS = """
    Vertical { height: 1fr; }
    #grid { height: 1fr; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; margin-left: 3; margin-top: 1; }
    """

    _ACTIONS: dict[str, tuple[str, tuple]] = {
        "d": ("_navigate", ("right", "No bitmap key to the right")),
        "a": ("_navigate", ("left", "No bitmap key to the left")),
        "s": ("_navigate", ("down", "No bitmap key below")),
        "w": ("_navigate", ("up", "No bitmap key above")),
        "h": ("_navigate", ("left", "No bitmap key to the left")),
        "j": ("_navigate", ("down", "No bitmap key below")),
        "k": ("_navigate", ("up", "No bitmap key above")),
        "l": ("_navigate", ("right", "No bitmap key to the right")),
        " ": ("_navigate", ("right", "No bitmap key to the right")),
        "space": ("_navigate", ("right", "No bitmap key to the right")),
        "enter": ("_select_current_key", ()),
        "^": ("_select_leftmost_in_row", ()),
        "circumflex_accent": ("_select_leftmost_in_row", ()),
        "$": ("_select_rightmost_in_row", ()),
        "dollar_sign": ("_select_rightmost_in_row", ()),
        "g": ("_handle_g_key", ()),
        "G": ("_select_last_row", ()),
        "z": ("_handle_z_key", ()),
        "left": ("_navigate", ("left", "No bitmap key to the left")),
        "right": ("_navigate", ("right", "No bitmap key to the right")),
        "up": ("_navigate", ("up", "No bitmap key above")),
        "down": ("_navigate", ("down", "No bitmap key below")),
        "F": ("_zero_fit_content", ()),
        "f": ("_zoom_to_key_selected", ()),
        "plus": ("_zoom_change", (1.25,)),
        "equals_sign": ("_zoom_change", (1.25,)),
        "minus": ("_zoom_change", (0.8,)),
        "underscore": ("_zoom_change", (0.8,)),
        "R": ("_reset_cursor_view", ()),
        "r": ("_reset_pan_view", ()),
        "tilde": ("_toggle_pan_mode", ()),
        "slash": ("_enter_find_mode", ()),
        "solidus": ("_enter_find_mode", ()),

    }

    _ACTION_KEYS: dict[str, tuple[str, tuple]] = {
        "p": ("_put_yanked_key", (True,)),
        "P": ("_put_yanked_key", (False,)),
        "v": ("_toggle_visual_mode", ()),
    }

    def __init__(self):
        super().__init__()
        self.zoom_scale = self.app.map_zoom if self.app.map_zoom is not None else 1.0
        self.aspect_y = 0.5
        self.pan_x, self.pan_y = self.app.map_pan
        self.pan_flip = self.app.map_pan_flip
        self.selected_key = self.app.current_key
        self._last_fit: str | None = None
        self._zoom_mode = False
        self._action_mode = self.app.action_mode
        self._mode_stack: list[str] = ["action"] if self._action_mode else []
        self._g_pending = False
        self._z_pending = False
        self._op_pending: str | None = None
        self._count_pending = 0
        self.cmd_mode = False
        self.cmd_buffer = ""
        self._yank_buffer = self.app.yank_buffer
        self._visual_mode = False
        self._visual_anchor: str | None = None
        self._ghost_mode = False
        self._ghost_x = 0
        self._ghost_y = 0
        self._saved_location: tuple[int, int] | None = None
        self._saved_bounds: dict | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.base_title), id="title")
        with Vertical():
            yield Static("", id="grid")
            yield Static("", id="hints", markup=False)
        yield Static("", id="status")

    def on_mount(self) -> None:
        if self.app.map_zoom is None:
            self.pan_x = 2
            self.pan_y = 3
        self.refresh_map()
        self._store_map_state()

    def on_screen_resume(self, _event) -> None:
        self._cancel_pending()
        if self.selected_key not in self.app.bitmaps:
            if self._saved_location and self._saved_bounds and self.app.bitmaps:
                nearest = self.app.find_nearest_key_at(self._saved_location, self._saved_bounds)
                self.selected_key = nearest or next(iter(self.app.bitmaps))
            elif self.app.bitmaps:
                self.selected_key = next(iter(self.app.bitmaps))
            else:
                self.selected_key = None
            self._saved_location = None
            self._saved_bounds = None
        self.query_one("#title", Static).update(
            self.app.title_with_file(self.base_title)
        )
        self.refresh_map()

    async def _on_resize(self, event: ResizeEvent) -> None:
        await super()._on_resize(event)
        self.refresh_map()

    def _store_map_state(self) -> None:
        setattr(self.app, "map_zoom", self.zoom_scale)
        setattr(self.app, "map_pan", (self.pan_x, self.pan_y))
        setattr(self.app, "map_pan_flip", self.pan_flip)
        setattr(self.app, "action_mode", self._action_mode)

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def compute_canvas_size(self) -> tuple[int, int]:
        g = self.query_one("#grid", Static)
        return max(2, g.size.width - 2), max(2, g.size.height)

    def _compute_virtual_bounds(self) -> tuple[float, float, float, float]:
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for data in self.app.bitmaps.values():
            loc = data.get("location", {})
            bx = loc.get("x", 0)
            by = loc.get("y", 0)
            bounds = data.get("bounds", {"width": 10, "height": 10})
            bw = bounds["width"]
            bh = bounds["height"]
            min_x = min(min_x, bx)
            min_y = min(min_y, by)
            max_x = max(max_x, bx + bw)
            max_y = max(max_y, by + bh)
        if min_x == float("inf"):
            return 0.0, 0.0, 10.0, 10.0
        return min_x, min_y, max_x - min_x, max_y - min_y

    def _zero_fit_content(self) -> None:
        cw, ch = self.compute_canvas_size()
        _, _, vw, vh = self._compute_virtual_bounds()
        if vw <= 0 or vh <= 0:
            return
        sx = (cw - 4) / vw
        sy = (ch - 5) / (vh * self.aspect_y)
        self.zoom_scale = max(0.1, min(sx, sy))
        self.pan_x = 2
        self.pan_y = 3
        self._last_fit = "zero"
        self.refresh_map()

    def _zoom_to_key(self, key: str) -> None:
        self._last_fit = None
        cw, ch = self.compute_canvas_size()
        data = self.app.bitmaps.get(key)
        if not data:
            return
        loc = data.get("location", {})
        bx = loc.get("x", 0)
        by = loc.get("y", 0)
        bounds = data.get("bounds", {"width": 10, "height": 10})
        bw = bounds["width"]
        bh = bounds["height"]
        target_w = int(cw * 0.95)
        target_h = int(ch * 0.95)
        sx = target_w / (bw + 2) if bw > 0 else 1
        sy = target_h / ((bh + 3) * self.aspect_y) if bh > 0 else 1
        self.zoom_scale = max(0.1, min(sx, sy))
        self.pan_x = int(cw / 2 - bx * self.zoom_scale - (bw * self.zoom_scale) / 2)
        self.pan_y = int(
            ch / 2
            - by * self.zoom_scale * self.aspect_y
            - (bh * self.zoom_scale * self.aspect_y) / 2
            + 1
        )
        self.selected_key = key
        self.refresh_map()

    def _key_pixel_rect(self) -> tuple[int, int, int, int] | None:
        data = self.app.bitmaps.get(self.selected_key)
        if not data:
            return None
        loc = data.get("location", {"x": 0, "y": 0})
        bounds = data.get("bounds", {"width": 10, "height": 10})
        left = int(loc.get("x", 0) * self.zoom_scale) + self.pan_x
        top = int(loc.get("y", 0) * self.zoom_scale * self.aspect_y) + self.pan_y
        width = int(bounds.get("width", 10) * self.zoom_scale)
        height = int(bounds.get("height", 10) * self.zoom_scale * self.aspect_y)
        return left, top, width, height

    def _pan_needed(self, cw: int, ch: int, padding: int = 2) -> tuple[int, int]:
        rect = self._key_pixel_rect()
        if rect is None:
            return 0, 0
        left, top, width, height = rect
        dx = 0
        if width < cw - 2 * padding:
            if left < padding:
                dx = padding - left
            elif left + width > cw - padding:
                dx = cw - padding - (left + width)
        dy = 0
        if height < ch - 2 * padding:
            if top < padding:
                dy = padding - top
            elif top + height > ch - padding:
                dy = ch - padding - (top + height)
        return dx, dy

    def _ensure_cursor_visible(self) -> bool:
        cw, ch = self.compute_canvas_size()
        dx, dy = self._pan_needed(cw, ch)
        if dx or dy:
            self.pan_x += dx
            self.pan_y += dy
            return True
        return False

    def _reveal_cursor(self) -> bool:
        cw, ch = self.compute_canvas_size()
        data = self.app.bitmaps.get(self.selected_key)
        if not data:
            return False
        loc = data.get("location", {"x": 0, "y": 0})
        bounds = data.get("bounds", {"width": 10, "height": 10})
        bx = loc.get("x", 0)
        by = loc.get("y", 0)
        bw = bounds.get("width", 10)
        bh = bounds.get("height", 10)
        left = int(bx * self.zoom_scale) + self.pan_x
        width = int(bw * self.zoom_scale)
        pan_x = self.pan_x
        if left + width < 0 or left > cw:
            dx, _ = self._pan_needed(cw, ch)
            pan_x = self.pan_x + dx
        pan_y = int(
            ch / 2
            - by * self.zoom_scale * self.aspect_y
            - (bh * self.zoom_scale * self.aspect_y) / 2
            + 1
        )
        if pan_x != self.pan_x or pan_y != self.pan_y:
            self.pan_x = pan_x
            self.pan_y = pan_y
            return True
        return False

    def _compute_positions(self, ctx: DeviceContext) -> dict:
        positions = {}
        for key, data in self.app.bitmaps.items():
            loc = data.get("location", {})
            bx = loc.get("x", 0)
            by = loc.get("y", 0)
            bounds = data.get("bounds", {"width": 10, "height": 10})
            bw = bounds["width"]
            bh = bounds["height"]
            pixel_left = int(bx * ctx.zoom_scale) + ctx.pan_x
            pixel_top = int(by * ctx.zoom_scale * ctx.aspect_y) + ctx.pan_y
            pixel_w = max(1, int(bw * ctx.zoom_scale))
            pixel_h = max(1, int(bh * ctx.zoom_scale * ctx.aspect_y))
            positions[key] = {
                "bx": bx,
                "by": by,
                "bw": bw,
                "bh": bh,
                "pixel_left": pixel_left,
                "pixel_top": pixel_top,
                "pixel_w": pixel_w,
                "pixel_h": pixel_h,
            }
        return positions

    def _get_bitmap_attrs(self, key: str) -> tuple[int, int, int, int, list]:
        data = self.app.bitmaps.get(key, {})
        loc = data.get("location", {})
        bx = loc.get("x", 0)
        by = loc.get("y", 0)
        bounds = data.get("bounds", {"width": 10, "height": 10})
        bw = bounds["width"]
        bh = bounds["height"]
        pixels = data.get("bitmap", {}).get("pixels", [])
        return bx, by, bw, bh, pixels

    def _count_pixels(
        self, pixels: list, px: tuple[int, int], py: tuple[int, int]
    ) -> dict:
        counts = {}
        for row_idx in range(py[0], py[1] + 1):
            if row_idx >= len(pixels):
                continue
            row = pixels[row_idx]
            for pcol in range(px[0], px[1] + 1):
                if pcol >= len(row):
                    continue
                ch = row[pcol]
                if ch != " ":
                    counts[ch] = counts.get(ch, 0) + 1
        return counts

    def _sample_pixel(
        self, ctx: DeviceContext, key: str, disp_col: int, disp_row: int
    ) -> str:
        bx, by, bw, bh, pixels = self._get_bitmap_attrs(key)
        scale_y = ctx.zoom_scale * ctx.aspect_y
        px = (
            max(0, int(math.floor(bx + disp_col / ctx.zoom_scale)) - bx),
            min(bw - 1, int(math.ceil(bx + (disp_col + 1) / ctx.zoom_scale)) - 1 - bx),
        )
        py = (
            max(0, int(math.floor(by + disp_row / scale_y)) - by),
            min(bh - 1, int(math.ceil(by + (disp_row + 1) / scale_y)) - 1 - by),
        )
        counts = self._count_pixels(pixels, px, py)
        if not counts:
            return " "
        max_c = max(counts.values())
        return max(
            (c for c, n in counts.items() if n == max_c), key=lambda c: int(c, 16)
        )

    def _pixel_map_char(self, pixel_char: str) -> tuple[str, str | None]:
        if pixel_char == " ":
            return " ", None
        color_entry = self.app.active_palette.get(pixel_char, {})
        hex_color = color_entry.get("hex", "")
        display_char = (
            color_entry.get("glyph", pixel_char) if self.app.glyphmode else pixel_char
        )
        if self.app.color_pixels == "on":
            return " ", f"on {hex_color}"
        if self.app.color_pixels == "mixed":
            return display_char, hex_color
        return display_char, None

    def _render_one(
        self, ctx: DeviceContext, key: str, pos: dict, *, cell, opts: dict
    ) -> None:
        pl = pos["pixel_left"]
        pt = pos["pixel_top"]
        dim = opts.get("dim", False)
        ghost = opts.get("ghost", False)
        frame_style = opts.get("frame_style")
        if frame_style is None:
            frame_style = "dim" if dim else (self.app.current_theme.primary or "#00ffff")

        def render_row(row: int) -> None:
            if ghost:
                return
            for col in range(pos["pixel_w"]):
                pixel_char = self._sample_pixel(ctx, key, col, row)
                display, px_style = self._pixel_map_char(pixel_char)
                if px_style and dim:
                    px_style = f"dim {px_style}"
                cell(pl + col, pt + row, display, px_style, False)

        for i, ch in enumerate(str(key)):
            if pl + i < ctx.pan_x - 1 or pt - 2 < ctx.pan_y - 2:
                break
            if pl + i > opts["bounds"][0] or pt - 2 > opts["bounds"][1]:
                break
            cell(pl + i, pt - 2, ch, "dim" if (dim or ghost) else None, True)
        cell(pl - 1, pt - 1, "╔" if not dim else "┌", frame_style, True)
        for cx in range(pl, pl + pos["pixel_w"]):
            cell(cx, pt - 1, "═" if not dim else "─", frame_style, True)
        cell(pl + pos["pixel_w"], pt - 1, "╗" if not dim else "┐", frame_style, True)
        cell(pl - 1, pt + pos["pixel_h"], "╚" if not dim else "└", frame_style, True)
        for cx in range(pl, pl + pos["pixel_w"]):
            cell(cx, pt + pos["pixel_h"], "═" if not dim else "─", frame_style, True)
        cell(
            pl + pos["pixel_w"],
            pt + pos["pixel_h"],
            "╝" if not dim else "┘",
            frame_style,
            True,
        )
        for row in range(pos["pixel_h"]):
            cell(pl - 1, pt + row, "║" if not dim else "│", frame_style, True)
            cell(
                pl + pos["pixel_w"],
                pt + row,
                "║" if not dim else "│",
                frame_style,
                True,
            )
            render_row(row)

    def _compute_scrolled(
        self, ctx: DeviceContext, positions: dict
    ) -> tuple[bool, bool, bool, bool, int, int]:
        max_right = 0
        max_bottom = 0
        min_left = float("inf")
        min_top = float("inf")
        for pos in positions.values():
            pl = pos["pixel_left"]
            pt = pos["pixel_top"]
            min_left = min(min_left, pl)
            min_top = min(min_top, pt)
            max_right = max(max_right, pl + pos["pixel_w"])
            max_bottom = max(max_bottom, pt + pos["pixel_h"])
        if min_left == float("inf"):
            min_left = min_top = 0
        scrolled_l = min_left < 1
        scrolled_r = max_right > ctx.cw - 2
        scrolled_u = min_top < 1
        scrolled_d = max_bottom > ctx.ch - 2
        return scrolled_l, scrolled_r, scrolled_u, scrolled_d, max_right, max_bottom

    def _render_grid(self, ctx: DeviceContext) -> Text:
        positions = self._compute_positions(ctx)
        grid = [[(" ", None) for _ in range(ctx.cw)] for _ in range(ctx.ch)]

        (scrolled_l, scrolled_r, scrolled_u, scrolled_d, max_right, max_bottom) = (
            self._compute_scrolled(ctx, positions)
        )

        def set_cell(
            col: int, row: int, char: str, style: str | None, overwrite: bool
        ) -> None:
            if 0 <= row < ctx.ch and 0 <= col < ctx.cw:
                if overwrite or grid[row][col][0] == " ":
                    grid[row][col] = (char, style)

        max_bounds = (max_right, max_bottom)
        visual_set = set(self._visual_selection())
        yanked_set = self._yanked_key_names()
        yank_style = self.app.current_theme.warning or "orange"
        for key, pos in positions.items():
            if key in visual_set or key == self.selected_key:
                continue
            opts: dict = {"bounds": max_bounds, "dim": True}
            if key in yanked_set:
                opts["dim"] = False
                opts["frame_style"] = yank_style
            self._render_one(
                ctx,
                key,
                pos,
                cell=set_cell,
                opts=opts,
            )
        for key in self._visual_selection():
            if key not in positions:
                continue
            opts: dict = {"bounds": max_bounds, "dim": False}
            if key == self.selected_key:
                opts["frame_style"] = "white"
            elif key in yanked_set:
                opts["frame_style"] = yank_style
            self._render_one(ctx, key, positions[key], cell=set_cell, opts=opts)
        if (
            self.selected_key in positions
            and self.selected_key not in visual_set
        ):
            self._render_one(
                ctx,
                self.selected_key,
                positions[self.selected_key],
                cell=set_cell,
                opts={"bounds": max_bounds, "dim": False},
            )

        if self._ghost_mode:
            self._render_ghost(ctx, set_cell, max_bounds)

        self._draw_grid_borders(
            ctx, grid, (scrolled_l, scrolled_r, scrolled_u, scrolled_d)
        )
        self._fill_grid_empty(ctx, grid, max_right, max_bottom)
        return self._compress_grid(ctx, grid)

    def _draw_grid_borders(
        self, ctx: DeviceContext, grid: list, scrolled: tuple[bool, bool, bool, bool]
    ) -> None:
        sl, sr, su, sd = scrolled
        indicator_style = "white"
        frame_style = "dim"
        for row in (0, ctx.ch - 1):
            tl, tr = ("┌", "┐") if row == 0 else ("└", "┘")
            for col in range(ctx.cw):
                if col == 0:
                    grid[row][col] = (tl, frame_style)
                elif col == ctx.cw - 1:
                    grid[row][col] = (tr, frame_style)
                elif sl and col == 1:
                    grid[row][col] = ("<", indicator_style)
                elif sr and col == ctx.cw - 2:
                    grid[row][col] = (">", indicator_style)
                else:
                    grid[row][col] = ("─", frame_style)
        for row in range(1, ctx.ch - 1):
            grid[row][0] = ("│", frame_style)
            grid[row][ctx.cw - 1] = ("│", frame_style)
        if su and ctx.ch > 2:
            grid[1][0] = ("^", indicator_style)
            grid[1][ctx.cw - 1] = ("^", indicator_style)
        if sd and ctx.ch > 2:
            grid[ctx.ch - 2][0] = ("v", indicator_style)
            grid[ctx.ch - 2][ctx.cw - 1] = ("v", indicator_style)

    def _fill_grid_empty(
        self, ctx: DeviceContext, grid: list, max_right: int, max_bottom: int
    ) -> None:
        for row in range(ctx.ch):
            for col in range(ctx.cw):
                if grid[row][col][0] != " ":
                    continue
                if col < ctx.pan_x - 1 or row < ctx.pan_y - 2:
                    grid[row][col] = ("█", "grey15")
                elif col > max_right or row > max_bottom:
                    grid[row][col] = ("█", "grey15")

    def _compress_grid(self, ctx: DeviceContext, grid: list) -> Text:
        result = Text()
        for row in range(ctx.ch):
            if row > 0:
                result.append("\n")
            col = 0
            while col < ctx.cw:
                _, st = grid[row][col]
                end = col + 1
                while end < ctx.cw and grid[row][end][1] == st:
                    end += 1
                segment = "".join(grid[row][k][0] for k in range(col, end))
                if st:
                    result.append(segment, style=st)
                else:
                    result.append(segment)
                col = end
        return result

    def _pan_available(self) -> bool:
        cw, ch = self.compute_canvas_size()
        _, _, vw, vh = self._compute_virtual_bounds()
        return (
            vw * self.zoom_scale > cw - 2
            or vh * self.zoom_scale * self.aspect_y > ch - 2
        )

    def _pan(self, dx: int, dy: int) -> None:
        self._last_fit = None
        if self.pan_flip:
            self.pan_x -= dx
            self.pan_y -= dy
        else:
            self.pan_x += dx
            self.pan_y += dy
        self.refresh_map()

    def refresh_map(self) -> None:
        cw, ch = self.compute_canvas_size()
        ctx = DeviceContext(
            cw=cw,
            ch=ch,
            zoom_scale=self.zoom_scale,
            aspect_y=self.aspect_y,
            pan_x=self.pan_x,
            pan_y=self.pan_y,
        )
        self.query_one("#grid", Static).update(self._render_grid(ctx))
        self.update_hints()
        self._store_map_state()

    def update_hints(self) -> None:
        self.query_one("#hints", Static).update(self._build_hints())

    def _build_hints(self) -> Text:
        hints = Text()
        unicode_arrows = "\u25b4\u25be\u25c2\u25b8"
        select_key_dim = None if (len(self.app.bitmaps) > 1) else "dim"
        zoom_on_off = "on" if self._zoom_mode else "off"
        action_on_off = "on" if self._action_mode else "off"
        ghost_on_off = "on" if self._ghost_mode else "off"
        zero_style = None if self._last_fit != "zero" else "dim"
        zoom_in_style = None if self.zoom_scale < 20.0 else "dim"
        zoom_out_style = None if self.zoom_scale > 0.1 else "dim"
        reset_zoom_style = None if self.zoom_scale != 1.0 else "dim"
        pan_label = "pan" if self.pan_flip else "scroll"
        reset_dim = None if (self.pan_x != 2 or self.pan_y != 3) else "dim"
        ghost_dim = None if self._yank_buffer is not None else "dim"

        if not self._zoom_mode:
            hints.append(f"[wasd/hjkl/{unicode_arrows}] select key  ", style=select_key_dim)
        else:
            hints.append("[wasd] select key  ", style=select_key_dim)
        hints.append("[/] find key  ")
        hints.append("[Enter] open key  ")
        hints.append(f"Key={self.selected_key}\n")

        hints.append("[⇧F]it all  ", style=zero_style)
        hints.append("[f]it selected key  ")
        hints.append("[+=] zoom  ", style=zoom_in_style)
        hints.append("[-_] zoom  ", style=zoom_out_style)
        if self._zoom_mode:
            hints.append("[0] reset zoom  ", style=reset_zoom_style)
        hints.append(f"Zoom={int(self.zoom_scale * 100)}%\n")

        hints.append(f"[⇧HJKL] fast {pan_label}  ")
        if self._zoom_mode:
            hints.append(f"[hjkl/{unicode_arrows}] slow {pan_label}  ")
        hints.append(f"[r]eset {pan_label}  ", style=reset_dim)
        hints.append("[R]eset to cursor\n", style=reset_dim)

        hints.append(f"[`] zoom ({zoom_on_off})  ")
        if self.pan_flip:
            hints.append("[~] *pan*/scroll  ")
        else:
            hints.append("[~] pan/*scroll*  ")
        hints.append(f"[!] action ({action_on_off})  ")
        hints.append(f"[@] ghost ({ghost_on_off})\n", style=ghost_dim)

        hints.append("[⇧O]ps  ")
        undo_style = None if self.app.history.map_can_undo() else "dim"
        redo_style = None if self.app.history.map_can_redo() else "dim"
        hints.append("[u]ndo  ", style=undo_style)
        hints.append("[⌃R]edo  ", style=redo_style)
        hints.append("[?] help  ")
        hints.append("[Escape] back")
        return hints

    def _zoom_change(self, factor: float) -> None:
        self._last_fit = None
        data = self.app.bitmaps.get(self.selected_key, {})
        loc = data.get("location", {})
        bx = loc.get("x", 0)
        by = loc.get("y", 0)
        bounds_ = data.get("bounds", {"width": 10, "height": 10})
        bw = bounds_["width"]
        bh = bounds_["height"]
        cx = bx * self.zoom_scale + self.pan_x + (bw * self.zoom_scale) / 2
        cy = (
            by * self.zoom_scale * self.aspect_y
            + self.pan_y
            + (bh * self.zoom_scale * self.aspect_y) / 2
        )
        new_s = self.zoom_scale * factor
        new_s = max(0.1, min(new_s, 20.0))
        self.zoom_scale = new_s
        ncx = bx * self.zoom_scale + self.pan_x + (bw * self.zoom_scale) / 2
        ncy = (
            by * self.zoom_scale * self.aspect_y
            + self.pan_y
            + (bh * self.zoom_scale * self.aspect_y) / 2
        )
        self.pan_x += int(cx - ncx)
        self.pan_y += int(cy - ncy)
        self.refresh_map()

    def _enter_find_mode(self) -> None:
        self.app.push_screen(FindKeyScreen(), self._on_find_key)

    def _on_bitmap_ops_result(self, result: str | None) -> None:
        if result == "n":
            self._new_key()
        elif result == "c":
            self._dup_key()
        elif result == "r":
            self._save_key_state()
            self.app.push_screen(ConfigKeyRenameScreen(key=self.selected_key))
        elif result == "d":
            self._save_key_state()
            self.app.push_screen(ConfigKeyDeleteScreen(key=self.selected_key))

    def _save_key_state(self) -> None:
        if self.selected_key in self.app.bitmaps:
            bm = self.app.bitmaps[self.selected_key]
            self._saved_location = self.app.get_location(bm)
            self._saved_bounds = bm.get("bounds", {"width": 10, "height": 10})
        else:
            self._saved_location = None
            self._saved_bounds = None

    def _new_key(self) -> None:
        self.app.push_screen(DirectionSelectScreen(), self._on_new_key_direction)

    def _dup_key(self) -> None:
        self.app.push_screen(DirectionSelectScreen(), self._on_dup_key_direction)

    def _on_new_key_direction(self, direction: str | None) -> None:
        if direction:
            self.app.push_screen(
                NewKeyScreen(direction, False, self.app.next_key_name(), self.selected_key)
            )

    def _on_dup_key_direction(self, direction: str | None) -> None:
        if direction:
            self.app.push_screen(
                NewKeyScreen(direction, True, self.app.next_key_name(), self.selected_key)
            )

    def _on_find_key(self, result: tuple[str, bool] | None) -> None:
        if result is not None:
            key, is_new = result
            self.selected_key = key
            if not is_new:
                self._zoom_to_key(key)
            else:
                self.refresh_map()

    def _navigate(self, direction: str, fail_msg: str) -> None:
        dest = self.app.navigate_key(direction, self.selected_key)
        if dest:
            self.selected_key = dest
            self._ensure_cursor_visible()
            self.refresh_map()
        else:
            self.show_status(fail_msg)

    def _navigate_repeat(self, direction: str, count: int, fail_msg: str) -> None:
        key = self.selected_key
        moved = False
        for _ in range(max(1, count)):
            dest = self.app.navigate_key(direction, key)
            if not dest or dest == key:
                break
            key = dest
            moved = True
        if moved:
            self.selected_key = key
            self._ensure_cursor_visible()
            self.refresh_map()
        else:
            self.show_status(fail_msg)

    def _select_first_key(self) -> None:
        keys = list(self.app.bitmaps.keys())
        if not keys:
            return
        locs = {
            k: self.app.bitmaps[k].get("location", {"x": 0, "y": 0})
            for k in keys
        }
        first = min(keys, key=lambda k: (locs[k].get("y", 0), locs[k].get("x", 0)))
        self.selected_key = first
        self._ensure_cursor_visible()
        self.refresh_map()

    def _select_last_row(self) -> None:
        keys = list(self.app.bitmaps.keys())
        if not keys:
            return
        locs = {k: self.app.bitmaps[k].get("location", {"x": 0, "y": 0}) for k in keys}
        rows = sorted(set(loc.get("y", 0) for loc in locs.values()))
        if not rows:
            return
        target_y = rows[-1]
        candidates = [k for k in keys if locs[k].get("y", 0) == target_y]
        best = min(candidates, key=lambda k: locs[k].get("x", 0))
        self.selected_key = best
        self._ensure_cursor_visible()
        self.refresh_map()

    def _select_leftmost_in_row(self) -> None:
        row = self._row_keys()
        if not row:
            return
        best = min(
            row, key=lambda k: self.app.get_location(self.app.bitmaps[k])[0]
        )
        self.selected_key = best
        self._ensure_cursor_visible()
        self.refresh_map()

    def _select_rightmost_in_row(self) -> None:
        row = self._row_keys()
        if not row:
            return
        best = max(
            row, key=lambda k: self.app.get_location(self.app.bitmaps[k])[0]
        )
        self.selected_key = best
        self._ensure_cursor_visible()
        self.refresh_map()

    def _handle_g_key(self) -> None:
        self._g_pending = True

    def _handle_z_key(self) -> None:
        self._z_pending = True

    def _select_viewport_leftmost(self) -> None:
        cw, ch = self.compute_canvas_size()
        ctx = DeviceContext(cw, ch, self.zoom_scale, self.aspect_y, self.pan_x, self.pan_y)
        positions = self._compute_positions(ctx)
        visible = []
        for key, pos in positions.items():
            px = pos["pixel_left"]
            pt = pos["pixel_top"]
            if pt < ch and pt + pos["pixel_h"] >= 0 and px >= 0:
                visible.append((key, px))
        if visible:
            self.selected_key = min(visible, key=lambda x: x[1])[0]
            self.refresh_map()

    def _select_viewport_rightmost(self) -> None:
        cw, ch = self.compute_canvas_size()
        ctx = DeviceContext(cw, ch, self.zoom_scale, self.aspect_y, self.pan_x, self.pan_y)
        positions = self._compute_positions(ctx)
        visible = []
        for key, pos in positions.items():
            px = pos["pixel_left"]
            pt = pos["pixel_top"]
            if pt < ch and pt + pos["pixel_h"] >= 0 and px < cw and px + pos["pixel_w"] >= 0:
                visible.append((key, pos["pixel_left"] + pos["pixel_w"]))
        if visible:
            self.selected_key = max(visible, key=lambda x: x[1])[0]
            self.refresh_map()

    def _select_nth_row(self, n: int) -> None:
        keys = list(self.app.bitmaps.keys())
        if not keys:
            return
        locs = {k: self.app.bitmaps[k].get("location", {"x": 0, "y": 0}) for k in keys}
        rows = sorted(set(loc.get("y", 0) for loc in locs.values()))
        n = max(n, 1)
        n = min(n, len(rows))
        target_y = rows[n - 1]
        candidates = [k for k in keys if locs[k].get("y", 0) == target_y]
        best = min(candidates, key=lambda k: locs[k].get("x", 0))
        self.selected_key = best
        self._ensure_cursor_visible()
        self.refresh_map()

    def _select_current_key(self) -> None:
        self.app.set_current_key(self.selected_key)
        self.app.pop_screen()

    def _zoom_to_key_selected(self) -> None:
        self._zoom_to_key(self.selected_key)

    def _reset_zoom_view(self) -> None:
        self.zoom_scale = 1.0
        cw, ch = self.compute_canvas_size()
        data = self.app.bitmaps.get(self.selected_key)
        if data:
            loc = data.get("location", {})
            bx = loc.get("x", 0)
            by = loc.get("y", 0)
            bounds = data.get("bounds", {"width": 10, "height": 10})
            bw = bounds["width"]
            bh = bounds["height"]
            self.pan_x = int(cw / 2 - bx - bw / 2)
            self.pan_y = int(ch / 2 - by * self.aspect_y - (bh * self.aspect_y) / 2 + 1)
        else:
            self.pan_x = 2
            self.pan_y = 3
        self._last_fit = None
        self.refresh_map()

    def _reset_pan_view(self) -> None:
        self.pan_x = 2
        self.pan_y = 3
        self._last_fit = None
        self.refresh_map()

    def _reset_cursor_view(self) -> None:
        if self._ensure_cursor_visible():
            self.refresh_map()

    def _toggle_pan_mode(self) -> None:
        self.pan_flip = not self.pan_flip
        self.update_hints()
        self.show_status("Pan mode on" if self.pan_flip else "Pan mode off")

    def _unique_name(self, base: str) -> str:
        if base not in self.app.bitmaps:
            return base
        n = 1
        while f"{base}_{n}" in self.app.bitmaps:
            n += 1
        return f"{base}_{n}"

    def _build_collection_buffer(self, kind: str, keys: list[str]) -> dict | None:
        if not keys:
            return None
        locs = {k: self.app.get_location(self.app.bitmaps[k]) for k in keys}
        bounds = {
            k: self.app.bitmaps[k].get("bounds", {"width": 10, "height": 10})
            for k in keys
        }
        min_x = min(locs[k][0] for k in keys)
        min_y = min(locs[k][1] for k in keys)
        items = []
        max_w = 0
        max_h = 0
        for k in keys:
            rel_x = locs[k][0] - min_x
            rel_y = locs[k][1] - min_y
            w = bounds[k].get("width", 10)
            h = bounds[k].get("height", 10)
            max_w = max(max_w, rel_x + w)
            max_h = max(max_h, rel_y + h)
            items.append(
                {
                    "name": k,
                    "data": copy.deepcopy(self.app.bitmaps[k]),
                    "rel_x": rel_x,
                    "rel_y": rel_y,
                    "w": w,
                    "h": h,
                }
            )
        return {
            "kind": kind,
            "items": items,
            "bbox": {"w": max_w, "h": max_h},
            "origin": {"x": min_x, "y": min_y},
        }

    def _build_single_buffer(self, key: str) -> dict | None:
        bm = self.app.bitmaps.get(key)
        if bm is None:
            return None
        data = copy.deepcopy(bm)
        bounds = data.get("bounds", {"width": 10, "height": 10})
        loc = self.app.get_location(bm)
        return {
            "kind": "single",
            "items": [
                {
                    "name": key,
                    "data": data,
                    "rel_x": 0,
                    "rel_y": 0,
                    "w": bounds.get("width", 10),
                    "h": bounds.get("height", 10),
                }
            ],
            "bbox": {"w": bounds.get("width", 10), "h": bounds.get("height", 10)},
            "origin": {"x": loc[0], "y": loc[1]},
        }

    def _set_yank_buffer(self, buf: dict | None) -> None:
        self._yank_buffer = buf
        setattr(self.app, "yank_buffer", buf)

    def _yank_selected_key(self) -> None:
        buf = self._build_single_buffer(self.selected_key)
        if buf is None:
            self.show_status("No key to yank")
            return
        self._set_yank_buffer(buf)
        self.show_status(f"Yanked '{self.selected_key}'")

    def _key_rect(self, key: str) -> tuple[int, int, int, int] | None:
        bm = self.app.bitmaps.get(key)
        if bm is None:
            return None
        x, y = self.app.get_location(bm)
        bounds = bm.get("bounds", {"width": 10, "height": 10})
        return x, y, bounds.get("width", 10), bounds.get("height", 10)

    def _row_groups(self) -> list[list[str]]:
        return self.app.row_groups()

    def _row_keys(self) -> list[str]:
        return self.app.row_keys(self.selected_key)

    def _col_keys(self) -> list[str]:
        my_rect = self._key_rect(self.selected_key)
        if my_rect is None:
            return []
        result = []
        for key, _bm in self.app.bitmaps.items():
            rect = self._key_rect(key)
            if rect is None:
                continue
            if self.app.ranges_overlap(
                rect[0], rect[0] + rect[2], my_rect[0], my_rect[0] + my_rect[2]
            ):
                result.append(key)
        result.sort(key=lambda k: self.app.get_location(self.app.bitmaps[k])[1])
        return result

    @staticmethod
    def _normalize_motion(key: str) -> str | None:
        key = key.strip()
        if key in ("", "space"):
            return "space"
        if key in ("l", "right"):
            return "l"
        if key in ("h", "left"):
            return "h"
        if key in ("j", "down"):
            return "j"
        if key in ("k", "up"):
            return "k"
        if key in ("^", "circumflex_accent", "6", "0"):
            return "^"
        if key in ("$", "dollar_sign", "4"):
            return "$"
        return None

    def _motion_keys(self, motion: str, count: int) -> list[str] | None:
        count = max(1, count)
        if motion in ("space", "l"):
            row = self._row_keys()
            if self.selected_key not in row:
                return None
            idx = row.index(self.selected_key)
            return row[idx : min(len(row), idx + count)]
        if motion == "h":
            row = self._row_keys()
            if self.selected_key not in row:
                return None
            idx = row.index(self.selected_key)
            return row[max(0, idx - count) : idx]
        if motion in ("j", "k"):
            col = self._col_keys()
            if self.selected_key not in col:
                return None
            idx = col.index(self.selected_key)
            if motion == "j":
                return col[idx : min(len(col), idx + count + 1)]
            return col[max(0, idx - count) : idx + 1]
        if motion == "^":
            row = self._row_keys()
            if self.selected_key not in row:
                return None
            return row[: row.index(self.selected_key) + 1]
        if motion == "$":
            row = self._row_keys()
            if self.selected_key not in row:
                return None
            return row[row.index(self.selected_key) :]
        return None

    def _apply_operator(self, op: str, keys: list[str]) -> None:
        keys = [k for k in keys if k in self.app.bitmaps]
        if not keys:
            self.show_status("No keys to operate on")
            self._op_pending = None
            self._count_pending = 0
            return
        buf = (
            self._build_single_buffer(keys[0])
            if len(keys) == 1
            else self._build_collection_buffer("range", keys)
        )
        self._set_yank_buffer(buf)
        if op == "y":
            self.show_status(f"Yanked {len(keys)} key{'s' if len(keys) > 1 else ''}")
        else:
            n = self._delete_keys(keys)
            self.show_status(f"Deleted {n} key{'s' if n != 1 else ''}")
        self._op_pending = None
        self._count_pending = 0
        self.refresh_map()

    def _yank_row(self) -> None:
        row = self._row_keys()
        if not row:
            self.show_status("No row to yank")
            return
        self._set_yank_buffer(self._build_collection_buffer("row", row))
        self.show_status(f"Yanked row ({len(row)} keys)")

    def _visual_selection(self) -> list[str]:
        if not self._visual_mode:
            return []
        anchor = self._visual_anchor or ""
        if anchor not in self.app.bitmaps or self.selected_key not in self.app.bitmaps:
            return []
        order = [key for group in self._row_groups() for key in group]
        try:
            a_idx = order.index(anchor)
            c_idx = order.index(self.selected_key)
        except ValueError:
            return []
        lo, hi = sorted((a_idx, c_idx))
        return order[lo : hi + 1]

    def _visual_enter(self) -> None:
        groups = self._row_groups()
        my_row = next((g for g in groups if self.selected_key in g), None)
        if my_row is None:
            return
        self.selected_key = my_row[-1]
        idx = groups.index(my_row)
        if idx + 1 < len(groups):
            self.selected_key = groups[idx + 1][0]
        self.refresh_map()
        self.show_status(f"Visual mode ({len(self._visual_selection())} selected)")

    def _toggle_visual_mode(self) -> None:
        if self._visual_mode:
            self._visual_mode = False
            self._visual_anchor = None
            self.show_status("Visual mode off")
        else:
            if self.selected_key not in self.app.bitmaps:
                self.show_status("No key to select")
                return
            self._visual_mode = True
            self._visual_anchor = self.selected_key
            self.show_status(
                f"Visual mode ({len(self._visual_selection())} selected)"
            )
        self.refresh_map()
        self.update_hints()

    def _yank_visual_selection(self) -> None:
        sel = self._visual_selection()
        if not sel:
            self.show_status("Nothing selected")
            return
        self._set_yank_buffer(self._build_collection_buffer("selection", sel))
        self._visual_mode = False
        self._visual_anchor = None
        self.refresh_map()
        self.update_hints()
        self.show_status(f"Yanked selection ({len(sel)} keys)")

    def _collection_rect(
        self, keys: list[str]
    ) -> tuple[tuple[int, int] | None, dict | None]:
        locs = {
            k: self.app.get_location(self.app.bitmaps[k])
            for k in keys
            if k in self.app.bitmaps
        }
        if not locs:
            return None, None
        bounds = {
            k: self.app.bitmaps[k].get("bounds", {"width": 10, "height": 10})
            for k in locs
        }
        min_x = min(locs[k][0] for k in locs)
        min_y = min(locs[k][1] for k in locs)
        max_x = max(locs[k][0] + bounds[k].get("width", 10) for k in locs)
        max_y = max(locs[k][1] + bounds[k].get("height", 10) for k in locs)
        return (min_x, min_y), {"width": max_x - min_x, "height": max_y - min_y}

    def _delete_keys(self, keys: list[str]) -> int:
        delete_set = set(k for k in keys if k in self.app.bitmaps)
        if not delete_set:
            return 0
        self.app.history.map_record(copy.deepcopy(self.app.bitmaps))
        center_loc, center_bounds = self._collection_rect(list(delete_set))
        for k in delete_set:
            del self.app.bitmaps[k]
        self.app.build_key_adjacency()
        self.app.mark_dirty()
        if center_loc and center_bounds and self.app.bitmaps:
            self.selected_key = self.app.find_nearest_key_at(
                center_loc, center_bounds
            )
        else:
            self.selected_key = None
        self.refresh_map()
        self.update_hints()
        return len(delete_set)

    def _delete_row(self) -> None:
        row = self._row_keys()
        if not row:
            self.show_status("No row to delete")
            return
        self._set_yank_buffer(self._build_collection_buffer("row", row))
        n = self._delete_keys(row)
        if n:
            self.show_status(f"Deleted row ({n} keys)")

    def _delete_visual_selection(self) -> None:
        sel = self._visual_selection()
        if not sel:
            return
        self._set_yank_buffer(self._build_collection_buffer("selection", sel))
        n = self._delete_keys(sel)
        self._visual_mode = False
        self._visual_anchor = None
        self.update_hints()
        if n:
            self.show_status(f"Deleted selection ({n} keys)")

    def _buffer_source_present(self) -> bool:
        buf = self._yank_buffer
        if buf is None:
            return False
        return any(item["name"] in self.app.bitmaps for item in buf["items"])

    def _yanked_key_names(self) -> set[str]:
        buf = self._yank_buffer
        if buf is None:
            return set()
        return {
            item["name"]
            for item in buf["items"]
            if item["name"] in self.app.bitmaps
        }

    def _anchor_put_location(
        self,
        direction: str,
        target_size: tuple[int, int],
        source_size: tuple[int, int],
    ) -> dict | None:
        if self._buffer_source_present():
            return self.app.find_nearby_location(
                self.selected_key, direction, *target_size
            )
        origin = self._yank_buffer["origin"]
        return self.app.find_location_near_rect(
            (origin["x"], origin["y"]),
            source_size,
            direction=direction,
            target_size=target_size,
        )

    def _put_yanked_key(self, after: bool = True) -> None:
        if self._yank_buffer is None:
            self.show_status("No yanked key to put")
            return
        if self._yank_buffer["kind"] == "single":
            self._put_single_key(after)
        else:
            self._put_collection(after)

    def _put_single_key(self, after: bool = True) -> None:
        item = self._yank_buffer["items"][0]
        direction = "right" if after else "left"
        loc = self._anchor_put_location(
            direction, (item["w"], item["h"]), (item["w"], item["h"])
        )
        if loc is None:
            self.show_status("No space in that direction")
            return
        self.app.history.map_record(copy.deepcopy(self.app.bitmaps))
        new_name = self._unique_name(item["name"])
        bm = copy.deepcopy(item["data"])
        bm["location"] = loc
        self.app.bitmaps[new_name] = bm
        self.app.build_key_adjacency()
        self.app.mark_dirty()
        self.selected_key = new_name
        self._ensure_cursor_visible()
        self.refresh_map()
        self.update_hints()
        self.show_status(f"Put '{new_name}'")

    def _put_collection(self, after: bool = True) -> None:
        direction = "right" if after else "left"
        bbox = self._yank_buffer["bbox"]
        items = self._yank_buffer["items"]
        loc = self._anchor_put_location(
            direction, (bbox["w"], bbox["h"]), (bbox["w"], bbox["h"])
        )
        if loc is None:
            self.show_status("No space in that direction")
            return
        self.app.history.map_record(copy.deepcopy(self.app.bitmaps))
        placed = []
        for item in items:
            new_name = self._unique_name(item["name"])
            bm = copy.deepcopy(item["data"])
            bm["location"] = {
                "x": loc["x"] + item["rel_x"],
                "y": loc["y"] + item["rel_y"],
            }
            self.app.bitmaps[new_name] = bm
            placed.append(new_name)
        self.app.build_key_adjacency()
        self.app.mark_dirty()
        self.selected_key = placed[0] if placed else None
        self._ensure_cursor_visible()
        self.refresh_map()
        self.update_hints()
        self.show_status(f"Put ({len(placed)} keys)")

    def _toggle_ghost_mode(self) -> None:
        if self._ghost_mode:
            self._exit_ghost_mode()
            return
        if self._yank_buffer is None:
            self.show_status("Nothing yanked to place")
            return
        self._enter_ghost_mode()

    def _enter_ghost_mode(self) -> None:
        buf = self._yank_buffer
        if buf is None or self.selected_key not in self.app.bitmaps:
            self.show_status("Select a key first")
            return
        self._cancel_pending()
        bx, by = self.app.get_location(self.app.bitmaps[self.selected_key])
        self._ghost_x = bx
        self._ghost_y = by
        self._ghost_mode = True
        self._update_mode_stack("ghost", True)
        self.refresh_map()
        self.update_hints()
        self.show_status("Ghost mode on - ? for help")

    def _exit_ghost_mode(self) -> None:
        self._ghost_mode = False
        self._cancel_pending()
        self.refresh_map()
        self.update_hints()
        self.show_status("Ghost mode off")

    def _ghost_visible_range(self) -> tuple[int, int]:
        buf = self._yank_buffer
        if buf is None:
            return 0, 0
        cw, _ch = self.compute_canvas_size()
        bw = buf["bbox"]["w"]
        vmin = math.ceil(-self.pan_x / self.zoom_scale)
        vmax = max(math.floor((cw - self.pan_x) / self.zoom_scale - bw), vmin)
        return vmin, vmax

    def _ghost_align_targets(self) -> tuple[list[int], list[int]]:
        if self._yank_buffer is None:
            return [], []
        cw, _ch = self.compute_canvas_size()
        bw = self._yank_buffer["bbox"]["w"]
        world_left, world_right = (
            -self.pan_x / self.zoom_scale,
            (cw - self.pan_x) / self.zoom_scale,
        )
        items = [
            (self.app.get_location(bm)[0], bm.get("bounds", {}).get("width", 10))
            for bm in self.app.bitmaps.values()
        ]
        lefts = [x for x, _w in items if x >= world_left and x + bw <= world_right]
        rights = [
            x + w - bw
            for x, w in items
            if x + w - bw >= world_left and x + w <= world_right
        ]
        return lefts, rights

    def _ghost_snap_lines(self) -> tuple[list[int], list[int]]:
        buf = self._yank_buffer
        if buf is None:
            return [], []
        bw = buf["bbox"]["w"]
        bh = buf["bbox"]["h"]
        gap = 2
        xs: set[int] = set()
        ys: set[int] = set()
        for bm in self.app.bitmaps.values():
            x, y = self.app.get_location(bm)
            bounds = bm.get("bounds", {"width": 10, "height": 10})
            w = bounds.get("width", 10)
            h = bounds.get("height", 10)
            xs.add(x)
            xs.add(x + w + gap)
            xs.add(x - bw - gap)
            xs.add(x + w - bw)
            ys.add(y)
            ys.add(y + h + gap)
            ys.add(y - bh - gap)
            ys.add(y + h - bh)
        return sorted(xs), sorted(ys)

    def _snap_next(
        self, value: int, lines: list[int], sign: int, step: int
    ) -> int:
        if sign == 0:
            return value
        if not lines:
            return value + sign * step
        if sign > 0:
            for ln in lines:
                if ln > value:
                    return ln
        else:
            for ln in reversed(lines):
                if ln < value:
                    return ln
        return value + sign * step

    def _handle_ghost_key(self, key: str) -> bool:
        if not self._ghost_mode:
            return False
        if self._accumulate_count(key):
            return True
        if key in ("enter", "\n"):
            self._count_pending = 0
            self._ghost_commit()
            return True
        key_low = key.lower()
        if key_low.startswith("shift+"):
            key_low = key_low[len("shift+"):]
        if key_low in ("^", "circumflex_accent", "6", "0", "$", "dollar_sign", "4"):
            self._count_pending = 0
            vmin, vmax = self._ghost_visible_range()
            xs, _ys = self._ghost_snap_lines()
            in_range = [x for x in xs if vmin <= x <= vmax]
            is_end = key_low in ("$", "dollar_sign", "4")
            if in_range:
                self._ghost_x = max(in_range) if is_end else min(in_range)
            else:
                self._ghost_x = vmax if is_end else vmin
            self.refresh_map()
            return True
        if key_low in ("[", "left_square_bracket", "]", "right_square_bracket"):
            self._count_pending = 0
            lefts, rights = self._ghost_align_targets()
            is_end = key_low in ("]", "right_square_bracket")
            cands = rights if is_end else lefts
            if cands:
                self._ghost_x = max(cands) if is_end else min(cands)
            self.refresh_map()
            return True
        if key_low in GHOST_MOVE_KEYS:
            count = max(1, self._count_pending)
            self._count_pending = 0
            has_shift = key.startswith("shift+") or key.isupper()
            dx, dy = GHOST_MOVE_KEYS[key_low]
            if has_shift:
                self._ghost_x += dx * count
                self._ghost_y += dy * count
            else:
                xs, ys = self._ghost_snap_lines()
                bbox = self._yank_buffer["bbox"]
                for _ in range(count):
                    self._ghost_x = self._snap_next(
                        self._ghost_x, xs, dx, bbox["w"] + 2
                    )
                    self._ghost_y = self._snap_next(
                        self._ghost_y, ys, dy, bbox["h"] + 2
                    )
            self.refresh_map()
        return True

    def _ghost_commit(self) -> None:
        buf = self._yank_buffer
        if buf is None:
            self._exit_ghost_mode()
            return
        bbox = buf["bbox"]
        min_x = self._ghost_x
        min_y = self._ghost_y
        if self.app.rect_overlaps_any(min_x, min_y, bbox["w"], bbox["h"]):
            self.show_status("No space at ghost location")
            self.refresh_map()
            return
        self.app.history.map_record(copy.deepcopy(self.app.bitmaps))
        if min_x < 0 or min_y < 0:
            shift_x = -min(min_x, 0)
            shift_y = -min(min_y, 0)
            self.app.shift_all_bitmaps(shift_x, shift_y)
            self._ghost_x += shift_x
            self._ghost_y += shift_y
            min_x += shift_x
            min_y += shift_y
        placed = []
        for item in buf["items"]:
            new_name = self._unique_name(item["name"])
            bm = copy.deepcopy(item["data"])
            bm["location"] = {
                "x": min_x + item["rel_x"],
                "y": min_y + item["rel_y"],
            }
            self.app.bitmaps[new_name] = bm
            placed.append(new_name)
        self.app.build_key_adjacency()
        self.app.mark_dirty()
        if placed:
            self.selected_key = placed[0]
        self._ensure_cursor_visible()
        self.refresh_map()
        self.update_hints()
        self.show_status(f"Placed ({len(placed)} keys)")

    def _ghost_positions(self, ctx: DeviceContext) -> list[dict]:
        buf = self._yank_buffer
        if buf is None:
            return []
        result = []
        for item in buf["items"]:
            result.append(
                {
                    "name": item["name"],
                    "pixel_left": (
                        int((self._ghost_x + item["rel_x"]) * ctx.zoom_scale)
                        + ctx.pan_x
                    ),
                    "pixel_top": (
                        int(
                            (self._ghost_y + item["rel_y"])
                            * ctx.zoom_scale
                            * ctx.aspect_y
                        )
                        + ctx.pan_y
                    ),
                    "pixel_w": max(1, int(item["w"] * ctx.zoom_scale)),
                    "pixel_h": max(1, int(item["h"] * ctx.zoom_scale * ctx.aspect_y)),
                }
            )
        return result

    def _render_ghost(self, ctx, set_cell, max_bounds: tuple) -> None:
        buf = self._yank_buffer
        if buf is None:
            return
        bbox = buf["bbox"]
        collides = self.app.rect_overlaps_any(
            self._ghost_x, self._ghost_y, bbox["w"], bbox["h"]
        )
        frame_style = "red" if collides else "green"
        for pos in self._ghost_positions(ctx):
            self._render_one(
                ctx,
                pos["name"],
                pos,
                cell=set_cell,
                opts={
                    "bounds": max_bounds,
                    "frame_style": frame_style,
                    "ghost": True,
                },
            )

    def _delete_selected_key(self) -> None:
        if self.selected_key not in self.app.bitmaps:
            return
        self.app.history.map_record(copy.deepcopy(self.app.bitmaps))
        buf = self._build_single_buffer(self.selected_key)
        if buf is not None:
            self._set_yank_buffer(buf)
        key = self.selected_key
        next_key = self.app.navigate_key("right", key)
        if next_key is None or next_key == key:
            next_key = self.app.navigate_key("left", key)
        if next_key is None or next_key == key:
            next_key = self.app.navigate_key("down", key)
        if next_key is None or next_key == key:
            next_key = self.app.navigate_key("up", key)
        if next_key == key:
            next_key = None
        del self.app.bitmaps[key]
        self.selected_key = next_key
        self.app.build_key_adjacency()
        self.app.mark_dirty()
        self.refresh_map()
        self.update_hints()
        self.show_status(f"Deleted '{key}'")

    def _restore_map_state(self, bitmaps: dict) -> None:
        self.app.set_bitmaps(copy.deepcopy(bitmaps))
        self.app.mark_dirty()
        if self.selected_key not in self.app.bitmaps:
            self.selected_key = next(iter(self.app.bitmaps), None)
        self.refresh_map()
        self.update_hints()

    def _handle_undo_keys(self, event) -> bool:
        if event.key in ("ctrl+z", "u"):
            self._undo()
            return True
        if event.key == "ctrl+r":
            self._redo()
            return True
        return False

    def _undo(self) -> None:
        current = copy.deepcopy(self.app.bitmaps)
        while True:
            previous = self.app.history.map_undo_pop()
            if previous is None:
                self.show_status("Already at oldest change")
                return
            if previous != current:
                break
            current = previous
        self.app.history.map_redo_push(current)
        self._restore_map_state(previous)
        total = (
            self.app.history.map_undo_depth() + self.app.history.map_redo_depth()
        )
        self.show_status(
            f"Before change #{self.app.history.map_undo_depth() + 1} of {total}"
        )

    def _redo(self) -> None:
        current = copy.deepcopy(self.app.bitmaps)
        while True:
            following = self.app.history.map_redo_pop()
            if following is None:
                self.show_status("Already at newest change")
                return
            if following != current:
                break
            current = following
        self.app.history.map_undo_push(current)
        self._restore_map_state(following)
        total = (
            self.app.history.map_undo_depth() + self.app.history.map_redo_depth()
        )
        self.show_status(
            f"After change #{self.app.history.map_undo_depth()} of {total}"
        )

    def _cancel_op_pending(self) -> None:
        self._op_pending = None
        self._count_pending = 0

    def _cancel_pending(self) -> None:
        self._op_pending = None
        self._g_pending = False
        self._z_pending = False
        self._count_pending = 0
        self._visual_mode = False
        self._visual_anchor = None
        self._ghost_mode = False
        self._update_mode_stack("ghost", False)
        self.show_status("")

    def _handle_visual_key(self, key: str) -> bool:
        if key == "y":
            self._yank_visual_selection()
            return True
        if key in ("d", "x"):
            self._delete_visual_selection()
            return True
        if key in (" ", "space"):
            self._navigate("right", "No bitmap key to the right")
            return True
        if key in ("enter", "\n"):
            self._visual_enter()
            return True
        if key == "v":
            self._toggle_visual_mode()
            return True
        return False

    def _handle_action_key(self, key: str) -> bool:
        if not self._action_mode:
            return False
        self._g_pending = False

        if self._visual_mode:
            return self._handle_visual_key(key)

        key_low = key.lower()

        if self._op_pending:
            count = self._count_pending or 1
            op = self._op_pending
            if key_low == op:
                rows = self._row_groups()
                my_row = next((g for g in rows if self.selected_key in g), None)
                if my_row is None:
                    self._cancel_op_pending()
                    self.show_status("No row to operate on")
                    return True
                row_idx = rows.index(my_row)
                keys = [k for group in rows[row_idx : row_idx + count] for k in group]
                self._apply_operator(op, keys)
                return True
            motion = self._normalize_motion(key_low)
            if motion is not None:
                keys = self._motion_keys(motion, count)
                if keys is None or not keys:
                    self._cancel_op_pending()
                    self.show_status("Nothing to operate on")
                    return True
                self._apply_operator(op, keys)
                return True
            self._cancel_op_pending()

        if key_low == "y":
            self._op_pending = "y"
            return True
        if key_low == "d":
            self._op_pending = "d"
            return True
        if key == "Y":
            self._apply_operator("y", self._row_keys())
            return True
        if key_low == "x":
            if self.selected_key in self.app.bitmaps:
                self._apply_operator("d", [self.selected_key])
            else:
                self.show_status("No key to delete")
            return True
        action = self._ACTION_KEYS.get(key)
        if action:
            getattr(self, action[0])(*action[1])
            return True
        return False

    def _handle_g_pending(self, key: str, key_low: str) -> bool:
        if not self._g_pending:
            return False
        self._g_pending = False
        if key == "g":
            if self._count_pending > 0:
                count = self._count_pending
                self._count_pending = 0
                self._select_nth_row(count)
            else:
                self._select_first_key()
            return True
        if key_low in ("^", "6", "circumflex_accent"):
            self._count_pending = 0
            self._select_viewport_leftmost()
            return True
        if key_low in ("$", "4", "dollar_sign"):
            self._count_pending = 0
            self._select_viewport_rightmost()
            return True
        self._count_pending = 0
        self.show_status("")
        return True

    def _handle_z_pending(self, key: str) -> bool:
        if not self._z_pending:
            return False
        self._z_pending = False
        if key == "z":
            if self._reveal_cursor():
                self.refresh_map()
            return True
        self.show_status("")
        return True

    def _accumulate_count(self, key: str) -> bool:
        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9") or (
            key == "0" and self._count_pending > 0
        ):
            self._count_pending = self._count_pending * 10 + int(key)
            self.show_status(str(self._count_pending))
            return True
        return False

    def _handle_count_prefix(self, key: str) -> bool:
        if self._count_pending <= 0:
            return False
        count = self._count_pending
        if key == "G":
            self._count_pending = 0
            self._select_nth_row(count)
            return True
        if key in ("^", "circumflex_accent", "$", "dollar_sign"):
            self._count_pending = 0
            return False
        if self._zoom_mode:
            self._count_pending = 0
            return False
        direction = {
            "h": ("left", "No bitmap key to the left"),
            "left": ("left", "No bitmap key to the left"),
            "l": ("right", "No bitmap key to the right"),
            " ": ("right", "No bitmap key to the right"),
            "space": ("right", "No bitmap key to the right"),
            "right": ("right", "No bitmap key to the right"),
            "j": ("down", "No bitmap key below"),
            "down": ("down", "No bitmap key below"),
            "k": ("up", "No bitmap key above"),
            "up": ("up", "No bitmap key above"),
        }.get(key)
        if direction:
            self._count_pending = 0
            self._navigate_repeat(direction[0], count, direction[1])
            return True
        return False

    def _handle_pan(self, key: str, key_low: str) -> bool:
        if key_low.startswith("shift+"):
            key_low = key_low[len("shift+"):]
        if key_low not in PAN_KEYS:
            return False
        has_shift = key.startswith("shift+") or key.isupper()
        if not self._zoom_mode and not has_shift:
            return False
        step = 5 if has_shift else 1
        dx, dy = PAN_KEYS[key_low]
        self._pan(dx * step, dy * step)
        return True

    def _handle_map_key(self, key: str, key_low: str) -> None:
        if key_low == "0":
            if self._zoom_mode:
                self._reset_zoom_view()
            else:
                self._select_leftmost_in_row()
            return
        action = self._ACTIONS.get(key) or self._ACTIONS.get(key_low)
        if action:
            method_name, args = action
            getattr(self, method_name)(*args)

    def _update_mode_stack(self, mode: str, active: bool) -> None:
        if active:
            if mode not in self._mode_stack:
                self._mode_stack.append(mode)
        elif mode in self._mode_stack:
            self._mode_stack.remove(mode)

    def _current_help_page(self) -> int | None:
        if not self._mode_stack:
            return None
        return {
            "action": MAP_PAGE_ACTION,
            "zoom": MAP_PAGE_ZOOM,
            "ghost": MAP_PAGE_GHOST,
        }.get(self._mode_stack[-1])

    def on_key(self, event) -> None:
        if handle_cmd_key(self, event):
            event.stop()
            return

        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if self._handle_undo_keys(event):
            return
        key = event.key
        if key == "escape":
            if (
                self._ghost_mode
                or self._visual_mode
                or self._op_pending
                or self._g_pending
                or self._z_pending
            ):
                was_ghost = self._ghost_mode
                self._cancel_pending()
                self.refresh_map()
                self.update_hints()
                if was_ghost:
                    self.show_status("Ghost mode off")
                return
            self.app.pop_screen()
            return

        if key == "@" or getattr(event, "character", None) == "@" or key == "at_sign":
            self._toggle_ghost_mode()
            return

        if key == "?" or getattr(event, "character", None) == "?":
            self.app.push_screen(
                HelpScreen(
                    mode="map",
                    page=self._current_help_page(),
                    zoom_mode=self._zoom_mode,
                )
            )
            return

        if self._ghost_mode:
            self._handle_ghost_key(key)
            return

        key_low = key.lower()

        if key == "O":
            self.app.push_screen(BitmapOpsScreen(), self._on_bitmap_ops_result)
            return

        if key in ("`", "grave_accent"):
            self._zoom_mode = not self._zoom_mode
            self._update_mode_stack("zoom", self._zoom_mode)
            self.refresh_map()
            self.update_hints()
            self.show_status("Zoom mode on" if self._zoom_mode else "Zoom mode off")
            return

        if key == "!" or getattr(event, "character", None) == "!":
            self._action_mode = not self._action_mode
            setattr(self.app, "action_mode", self._action_mode)
            self._update_mode_stack("action", self._action_mode)
            self._cancel_pending()
            self.refresh_map()
            self.update_hints()
            if self._action_mode:
                self.show_status("Action mode on! - ? for help")
            else:
                self.show_status("Action mode off")
            return

        if self._accumulate_count(key):
            return

        if (
            self._handle_action_key(key)
            or self._handle_g_pending(key, key_low)
            or self._handle_z_pending(key)
            or self._handle_count_prefix(key)
            or self._handle_pan(key, key_low)
        ):
            return

        self._handle_map_key(key, key_low)
