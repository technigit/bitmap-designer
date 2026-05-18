"""Spatial overview screen showing all bitmap keys on a virtual canvas."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Resize as ResizeEvent
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

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


# pylint: disable=too-many-instance-attributes
class MapScreen(Screen):
    """Overview map of all bitmaps arranged by spatial location."""
    base_title = "Bitmap Map"
    CSS = """
    Vertical { height: 1fr; }
    #grid { height: 1fr; }
    #hints { opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.zoom_scale = self.app.map_zoom if self.app.map_zoom is not None else 1.0
        self._aspect_y = 0.5
        self.pan_x, self.pan_y = self.app.map_pan
        self.pan_flip = self.app.map_pan_flip
        self.selected_key = self.app.current_key
        self._find_mode = False
        self._find_buffer = ""
        self._last_fit: str | None = None

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
        self._update()
        self._store_map_state()

    async def _on_resize(self, event: ResizeEvent) -> None:
        await super()._on_resize(event)
        self._update()

    # pylint: disable=attribute-defined-outside-init
    def _store_map_state(self) -> None:
        self.app.map_zoom = self.zoom_scale
        self.app.map_pan = (self.pan_x, self.pan_y)
        self.app.map_pan_flip = self.pan_flip

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

    # pylint: disable=too-many-locals
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

    # pylint: disable=too-many-locals
    def _sample_pixel(self, ctx: DeviceContext, key: str,
                      disp_col: int, disp_row: int) -> str:
        data = self.app.bitmaps.get(key, {})
        loc = data.get("location", {})
        bx = loc.get("x", 0)
        by = loc.get("y", 0)
        bounds = data.get("bounds", {"width": 10, "height": 10})
        bw = bounds["width"]
        bh = bounds["height"]
        pixels = data.get("bitmap", {}).get("pixels", [])
        vx_s = bx + disp_col / ctx.zoom_scale
        vx_e = bx + (disp_col + 1) / ctx.zoom_scale
        vy_s = by + disp_row / (ctx.zoom_scale * ctx.aspect_y)
        vy_e = by + (disp_row + 1) / (ctx.zoom_scale * ctx.aspect_y)
        px_s = max(0, int(math.floor(vx_s)) - bx)
        px_e = min(bw - 1, int(math.ceil(vx_e)) - 1 - bx)
        py_s = max(0, int(math.floor(vy_s)) - by)
        py_e = min(bh - 1, int(math.ceil(vy_e)) - 1 - by)
        counts = {}
        for py in range(py_s, py_e + 1):
            if py >= len(pixels):
                continue
            row = pixels[py]
            for pcol in range(px_s, px_e + 1):
                if pcol >= len(row):
                    continue
                ch = row[pcol]
                if ch != " ":
                    counts[ch] = counts.get(ch, 0) + 1
        if not counts:
            return " "
        max_c = max(counts.values())
        best = max((c for c, n in counts.items() if n == max_c),
                   key=lambda c: int(c, 16))
        return best

    # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
    def _render_one(self, ctx: DeviceContext, key: str, pos: dict, cell,
                    style: str | None, overwrite: bool) -> None:
        p = pos
        pl = p["pixel_left"]
        pt = p["pixel_top"]
        pw = p["pixel_w"]
        ph = p["pixel_h"]
        bl = pl - 1
        br = pl + pw
        bt = pt - 1
        bb = pt + ph
        lr = pt - 2
        for i, ch in enumerate(str(key)):
            cell(bl + 1 + i, lr, ch, style, overwrite)
        cell(bl, bt, "+", style, overwrite)
        for cx in range(pl, br):
            cell(cx, bt, "-", style, overwrite)
        cell(br, bt, "+", style, overwrite)
        cell(bl, bb, "+", style, overwrite)
        for cx in range(pl, br):
            cell(cx, bb, "-", style, overwrite)
        cell(br, bb, "+", style, overwrite)
        for row in range(ph):
            cy = pt + row
            cell(bl, cy, "|", style, overwrite)
            cell(br, cy, "|", style, overwrite)
            for col in range(pw):
                cx = pl + col
                pxch = self._sample_pixel(ctx, key, col, row)
                cell(cx, cy, pxch, style, overwrite)

    # pylint: disable=too-many-branches
    def _render_grid(self, ctx: DeviceContext) -> Text:
        positions = self._compute_positions(ctx)
        grid = [[(" ", None) for _ in range(ctx.cw)]
                for _ in range(ctx.ch)]

        def set_cell(col: int, row: int, char: str, style: str | None,
                     overwrite: bool) -> None:
            if 0 <= row < ctx.ch and 0 <= col < ctx.cw:
                if overwrite or grid[row][col][0] == " ":
                    grid[row][col] = (char, style)

        for key, pos in positions.items():
            if key != self.selected_key:
                self._render_one(ctx, key, pos, set_cell, "dim", False)
        if self.selected_key in positions:
            self._render_one(ctx, self.selected_key, positions[self.selected_key],
                             set_cell, None, True)

        max_right = 0
        max_bottom = 0
        for pos in positions.values():
            r = pos["pixel_left"] + pos["pixel_w"]
            b = pos["pixel_top"] + pos["pixel_h"]
            max_right = max(max_right, r)
            max_bottom = max(max_bottom, b)

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

        for row in range(ctx.ch):
            for col in range(ctx.cw):
                if grid[row][col][0] != " ":
                    continue
                if col < ctx.pan_x - 1 or row < ctx.pan_y - 2:
                    grid[row][col] = ("█", "grey15")
                elif col > max_right or row > max_bottom:
                    grid[row][col] = ("█", "grey15")

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
        pan_style = None if self._pan_available() else "dim"
        pan_label = "pan" if self.pan_flip else "scroll"
        hints.append(f"[hjkl] {pan_label}" if pan_style is None else f"[hjkl] {pan_label}",
                     style=pan_style)
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
        self._find_mode = True
        self._find_buffer = ""
        msg = "Find key: (type key name)"
        self.query_one("#grid", Static).update(msg)

    def _exit_find_mode(self) -> None:
        self._find_mode = False
        self._find_buffer = ""
        self._update()

    def _navigate(self, direction: str, fail_msg: str) -> None:
        dest = self.app.navigate_key(direction, self.selected_key)
        if dest:
            self.selected_key = dest
            self._update()
        else:
            self.show_status(fail_msg)

    def _handle_find_key(self, key: str) -> None:
        if key == "enter":
            k = self._find_buffer.strip()
            if k in self.app.bitmaps:
                self.selected_key = k
                self._zoom_to_key(k)
                self._exit_find_mode()
            else:
                self.show_status(f"Key '{k}' not found.")
                self._exit_find_mode()
        elif key == "backspace":
            self._find_buffer = self._find_buffer[:-1]
            msg = f"Find key: {self._find_buffer or '(type key name)'}"
            self.query_one("#grid", Static).update(msg)
        elif len(key) == 1:
            self._find_buffer += key
            self.query_one("#grid", Static).update(f"Find key: {self._find_buffer}")

    # pylint: disable=too-many-branches
    def _handle_map_key(self, key: str, key_low: str) -> None:
        if key_low in ("d", "a", "s", "w"):
            dirs = {"d": ("right", "to the right"),
                    "a": ("left", "to the left"),
                    "s": ("down", "below"),
                    "w": ("up", "above")}
            d, msg = dirs[key_low]
            self._navigate(d, f"No bitmap key {msg}")
        elif key == "enter":
            self.app.set_current_key(self.selected_key)
            self.app.pop_screen()
        elif key == "F":
            self._zero_fit_content()
        elif key == "f":
            self._zoom_to_key(self.selected_key)
        elif key in ("plus", "equals_sign"):
            self._zoom_change(1.25)
        elif key in ("minus", "underscore"):
            self._zoom_change(0.8)
        elif key_low == "0":
            self.zoom_scale = 1.0
            self._last_fit = None
            self._update()
        elif key_low == "r":
            self.pan_x = 2
            self.pan_y = 3
            self._last_fit = None
            self._update()
        elif key_low == "h":
            self._pan(-1, 0)
        elif key_low == "l":
            self._pan(1, 0)
        elif key_low == "k":
            self._pan(0, -1)
        elif key_low == "j":
            self._pan(0, 1)
        elif key_low == "p":
            self.pan_flip = not self.pan_flip
            self._update_hints()
        elif key in ("slash", "solidus"):
            self._enter_find_mode()

    def on_key(self, event) -> None:
        key = event.key
        if key == "escape":
            if self._find_mode:
                self._exit_find_mode()
            else:
                self.app.pop_screen()
            return
        if self._find_mode:
            self._handle_find_key(key)
            return
        self._handle_map_key(key, key.lower())
