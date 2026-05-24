"""Spatial overview screen showing all bitmap keys on a virtual canvas."""
from __future__ import annotations
import math
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Resize as ResizeEvent
from textual.screen import Screen
from textual.widgets import Input, Static
from textual.containers import Vertical

from .popup_screen import PopupScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp

BORDER = "dim"


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
            self.input = Input(placeholder="Type key name...", id="find-input")
            yield self.input
            yield Static("", id="matches")
            yield Static("[Enter] select  [Escape] cancel", id="hints", markup=False)
            yield Static("", id="status")

    def on_screen_resume(self, _event) -> None:
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
            if val in self.app.bitmaps:
                self.dismiss(val)
            else:
                self.show_status(f"Key '{val}' not found.")


class MapScreen(Screen):
    """Overview map of all bitmaps arranged by spatial location."""
    base_title = "Map Mode"
    CSS = """
    Vertical { height: 1fr; }
    #grid { height: 1fr; }
    #hints { opacity: 0.5; }
    #status { dock: bottom; margin-left: 3; }
    """

    _ACTIONS: dict[str, tuple[str, tuple]] = {
        "d": ("_navigate", ("right", "No bitmap key to the right")),
        "a": ("_navigate", ("left", "No bitmap key to the left")),
        "s": ("_navigate", ("down", "No bitmap key below")),
        "w": ("_navigate", ("up", "No bitmap key above")),
        "enter": ("_select_current_key", ()),
        "F": ("_zero_fit_content", ()),
        "f": ("_zoom_to_key_selected", ()),
        "plus": ("_zoom_change", (1.25,)),
        "equals_sign": ("_zoom_change", (1.25,)),
        "minus": ("_zoom_change", (0.8,)),
        "underscore": ("_zoom_change", (0.8,)),
        "0": ("_reset_zoom_view", ()),
        "r": ("_reset_pan_view", ()),
        "h": ("_pan", (-1, 0)),
        "l": ("_pan", (1, 0)),
        "k": ("_pan", (0, -1)),
        "j": ("_pan", (0, 1)),
        "p": ("_toggle_pan_mode", ()),
        "slash": ("_enter_find_mode", ()),
        "solidus": ("_enter_find_mode", ()),
    }

    def __init__(self):
        super().__init__()
        self.zoom_scale = self.app.map_zoom if self.app.map_zoom is not None else 1.0
        self._aspect_y = 0.5
        self.pan_x, self.pan_y = self.app.map_pan
        self.pan_flip = self.app.map_pan_flip
        self.selected_key = self.app.current_key
        self._last_fit: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.base_title), id="title")
        with Vertical():
            yield Static("", id="grid")
            yield Static("", id="hints", markup=False)
        yield Static("")
        yield Static("", id="status")

    def on_mount(self) -> None:
        if self.app.map_zoom is None:
            self.pan_x = 2
            self.pan_y = 3
        self._update()
        self._store_map_state()

    async def _on_resize(self, event: ResizeEvent) -> None:
        await super()._on_resize(event)
        self._update()

    def _store_map_state(self) -> None:
        setattr(self.app, "map_zoom", self.zoom_scale)
        setattr(self.app, "map_pan", (self.pan_x, self.pan_y))
        setattr(self.app, "map_pan_flip", self.pan_flip)

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _compute_canvas_size(self) -> tuple[int, int]:
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
        cw, ch = self._compute_canvas_size()
        _, _, vw, vh = self._compute_virtual_bounds()
        if vw <= 0 or vh <= 0:
            return
        sx = (cw - 4) / vw
        sy = (ch - 5) / (vh * self._aspect_y)
        self.zoom_scale = max(0.1, min(sx, sy))
        self.pan_x = 2
        self.pan_y = 3
        self._last_fit = "zero"
        self._update()

    def _zoom_to_key(self, key: str) -> None:
        self._last_fit = None
        cw, ch = self._compute_canvas_size()
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
        sy = target_h / ((bh + 3) * self._aspect_y) if bh > 0 else 1
        self.zoom_scale = max(0.1, min(sx, sy))
        self.pan_x = int(cw / 2 - bx * self.zoom_scale - (bw * self.zoom_scale) / 2)
        self.pan_y = int(ch / 2 - by * self.zoom_scale * self._aspect_y
                         - (bh * self.zoom_scale * self._aspect_y) / 2)
        self.selected_key = key
        self._update()

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
                "bx": bx, "by": by, "bw": bw, "bh": bh,
                "pixel_left": pixel_left, "pixel_top": pixel_top,
                "pixel_w": pixel_w, "pixel_h": pixel_h,
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

    def _count_pixels(self, pixels: list, px: tuple[int, int],
                      py: tuple[int, int]) -> dict:
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

    def _sample_pixel(self, ctx: DeviceContext, key: str,
                      disp_col: int, disp_row: int) -> str:
        bx, by, bw, bh, pixels = self._get_bitmap_attrs(key)
        scale_y = ctx.zoom_scale * ctx.aspect_y
        px = (max(0, int(math.floor(bx + disp_col / ctx.zoom_scale)) - bx),
              min(bw - 1, int(math.ceil(bx + (disp_col + 1) / ctx.zoom_scale)) - 1 - bx))
        py = (max(0, int(math.floor(by + disp_row / scale_y)) - by),
              min(bh - 1, int(math.ceil(by + (disp_row + 1) / scale_y)) - 1 - by))
        counts = self._count_pixels(pixels, px, py)
        if not counts:
            return " "
        max_c = max(counts.values())
        return max((c for c, n in counts.items() if n == max_c),
                   key=lambda c: int(c, 16))

    def _render_one(self, ctx: DeviceContext, key: str, pos: dict,
                    cell, *, max_bounds: tuple[int, int]) -> None:
        pl = pos["pixel_left"]
        pt = pos["pixel_top"]
        pw = pos["pixel_w"]
        for i, ch in enumerate(str(key)):
            if pl + i < ctx.pan_x - 1 or pt - 2 < ctx.pan_y - 2:
                break
            if pl + i > max_bounds[0] or pt - 2 > max_bounds[1]:
                break
            cell(pl + i, pt - 2, ch)
        cell(pl - 1, pt - 1, "+")
        for cx in range(pl, pl + pw):
            cell(cx, pt - 1, "-")
        cell(pl + pw, pt - 1, "+")
        cell(pl - 1, pt + pos["pixel_h"], "+")
        for cx in range(pl, pl + pw):
            cell(cx, pt + pos["pixel_h"], "-")
        cell(pl + pw, pt + pos["pixel_h"], "+")
        for row in range(pos["pixel_h"]):
            cell(pl - 1, pt + row, "|")
            cell(pl + pw, pt + row, "|")
            for col in range(pw):
                cell(pl + col, pt + row,
                     self._sample_pixel(ctx, key, col, row))

    def _render_grid(self, ctx: DeviceContext) -> Text:
        positions = self._compute_positions(ctx)
        grid = [[(" ", None) for _ in range(ctx.cw)]
                for _ in range(ctx.ch)]

        max_right = 0
        max_bottom = 0
        for pos in positions.values():
            r = pos["pixel_left"] + pos["pixel_w"]
            b = pos["pixel_top"] + pos["pixel_h"]
            max_right = max(max_right, r)
            max_bottom = max(max_bottom, b)

        def set_cell(col: int, row: int, char: str, style: str | None,
                     overwrite: bool) -> None:
            if 0 <= row < ctx.ch and 0 <= col < ctx.cw:
                if overwrite or grid[row][col][0] == " ":
                    grid[row][col] = (char, style)

        max_bounds = (max_right, max_bottom)
        for key, pos in positions.items():
            if key != self.selected_key:
                self._render_one(ctx, key, pos,
                                 partial(set_cell, style="dim", overwrite=False),
                                 max_bounds=max_bounds)
        if self.selected_key in positions:
            self._render_one(ctx, self.selected_key, positions[self.selected_key],
                             partial(set_cell, style=None, overwrite=True),
                             max_bounds=max_bounds)

        self._draw_grid_borders(ctx, grid)
        self._fill_grid_empty(ctx, grid, max_right, max_bottom)
        return self._compress_grid(ctx, grid)

    def _draw_grid_borders(self, ctx: DeviceContext, grid: list) -> None:
        for col in range(ctx.cw):
            grid[0][col] = ("─", BORDER)
            grid[ctx.ch - 1][col] = ("─", BORDER)
        for row in range(1, ctx.ch - 1):
            grid[row][0] = ("│", BORDER)
            grid[row][ctx.cw - 1] = ("│", BORDER)
        grid[0][0] = ("┌", BORDER)
        grid[0][ctx.cw - 1] = ("┐", BORDER)
        grid[ctx.ch - 1][0] = ("└", BORDER)
        grid[ctx.ch - 1][ctx.cw - 1] = ("┘", BORDER)

    def _fill_grid_empty(self, ctx: DeviceContext, grid: list,
                         max_right: int, max_bottom: int) -> None:
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
        cw, ch = self._compute_canvas_size()
        _, _, vw, vh = self._compute_virtual_bounds()
        return (vw * self.zoom_scale > cw - 2 or
                vh * self.zoom_scale * self._aspect_y > ch - 2)


    def _pan(self, dx: int, dy: int) -> None:
        self._last_fit = None
        if self.pan_flip:
            self.pan_x -= dx
            self.pan_y -= dy
        else:
            self.pan_x += dx
            self.pan_y += dy
        self._update()

    def _update(self) -> None:
        cw, ch = self._compute_canvas_size()
        ctx = DeviceContext(cw=cw, ch=ch, zoom_scale=self.zoom_scale,
                            aspect_y=self._aspect_y, pan_x=self.pan_x,
                            pan_y=self.pan_y)
        self.query_one("#grid", Static).update(self._render_grid(ctx))
        self._update_hints()
        self._store_map_state()

    def _update_hints(self) -> None:
        hints = Text()
        hints.append("[wasd] select key  ")
        hints.append("[/] find key  ")
        hints.append("[Enter] switch key\n")
        zoom_in_style = None if self.zoom_scale < 20.0 else "dim"
        hints.append("[+=] zoom in  ", style=zoom_in_style)
        zoom_out_style = None if self.zoom_scale > 0.1 else "dim"
        hints.append("[-_] zoom out  ", style=zoom_out_style)
        reset_zoom_style = None if self.zoom_scale != 1.0 else "dim"
        hints.append("[0] reset zoom  ", style=reset_zoom_style)
        hints.append("\n")
        zero_style = None if self._last_fit != "zero" else "dim"
        hints.append("[⇧F]it all  ", style=zero_style)
        hints.append("[F]it key selection\n")
        pan_label = "pan" if self.pan_flip else "scroll"
        hints.append(f"[hjkl] {pan_label}")
        hints.append("  ")
        reset_pan_style = None if self.pan_x != 2 or self.pan_y != 3 else "dim"
        hints.append(f"[R]eset {'pan' if self.pan_flip else 'scroll'}",
                     style=reset_pan_style)
        hints.append("  ")
        hints.append("[Escape] back\n")
        hints.append(f"[P]an {'on' if self.pan_flip else 'off'}  ")
        hints.append(f"Key={self.selected_key}  ")
        hints.append(f"Zoom={int(self.zoom_scale * 100)}%")
        self.query_one("#hints", Static).update(hints)

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
        cy = (by * self.zoom_scale * self._aspect_y + self.pan_y
              + (bh * self.zoom_scale * self._aspect_y) / 2)
        new_s = self.zoom_scale * factor
        new_s = max(0.1, min(new_s, 20.0))
        self.zoom_scale = new_s
        ncx = bx * self.zoom_scale + self.pan_x + (bw * self.zoom_scale) / 2
        ncy = (by * self.zoom_scale * self._aspect_y + self.pan_y
               + (bh * self.zoom_scale * self._aspect_y) / 2)
        self.pan_x += int(cx - ncx)
        self.pan_y += int(cy - ncy)
        self._update()

    def _enter_find_mode(self) -> None:
        self.app.push_screen(FindKeyScreen(), self._on_find_key)

    def _on_find_key(self, result: str | None) -> None:
        if result is not None:
            self.selected_key = result
            self._zoom_to_key(result)

    def _navigate(self, direction: str, fail_msg: str) -> None:
        dest = self.app.navigate_key(direction, self.selected_key)
        if dest:
            self.selected_key = dest
            self._update()
        else:
            self.show_status(fail_msg)

    def _select_current_key(self) -> None:
        self.app.set_current_key(self.selected_key)
        self.app.pop_screen()

    def _zoom_to_key_selected(self) -> None:
        self._zoom_to_key(self.selected_key)

    def _reset_zoom_view(self) -> None:
        self.zoom_scale = 1.0
        self._last_fit = None
        self._update()

    def _reset_pan_view(self) -> None:
        self.pan_x = 2
        self.pan_y = 3
        self._last_fit = None
        self._update()

    def _toggle_pan_mode(self) -> None:
        self.pan_flip = not self.pan_flip
        self._update_hints()

    def _handle_map_key(self, key: str, key_low: str) -> None:
        action = self._ACTIONS.get(key) or self._ACTIONS.get(key_low)
        if action:
            method_name, args = action
            getattr(self, method_name)(*args)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        key = event.key
        if key == "escape":
            self.app.pop_screen()
            return
        self._handle_map_key(key, key.lower())
