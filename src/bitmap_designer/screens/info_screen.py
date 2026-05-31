"""Metadata info screen — :info command popup."""
from __future__ import annotations
import math
import os
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from .popup_screen import PopupScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _count_filled(pixels: list[str]) -> int:
    return sum(1 for row in pixels for ch in row if ch != " ")


def _file_info(app) -> dict:
    data = {}
    data["filename"] = app.file.basename if app.file.current_file else "Unsaved"
    if app.file.current_file and os.path.exists(app.file.current_file):
        data["filesize"] = os.path.getsize(app.file.current_file)
    else:
        data["filesize"] = None
    data["dirty"] = app.dirty
    return data


def _current_key_info(app, current_key: str) -> dict:
    bm = app.bitmaps.get(current_key, {})
    bounds = bm.get("bounds", {"width": 0, "height": 0})
    loc = bm.get("location", {"x": 0, "y": 0})
    pixels = bm.get("bitmap", {}).get("pixels", [])
    w, h = bounds.get("width", 0), bounds.get("height", 0)
    key_filled = _count_filled(pixels)
    return {
        "current_key": current_key,
        "key_bounds": (w, h),
        "key_location": (loc.get("x", 0), loc.get("y", 0)),
        "key_filled": key_filled,
        "key_total": w * h,
    }


def _pixel_counts(app) -> dict:
    total_area = 0
    total_filled = 0
    for bm_data in app.bitmaps.values():
        b = bm_data.get("bounds", {"width": 0, "height": 0})
        bkw, bkh = b.get("width", 0), b.get("height", 0)
        total_area += bkw * bkh
        total_filled += _count_filled(bm_data.get("bitmap", {}).get("pixels", []))
    return {"total_pixel_area": total_area, "total_filled": total_filled}


def _canvas_frame(app) -> dict:
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    has_bitmaps = False
    for bm_data in app.bitmaps.values():
        loc = bm_data.get("location", {})
        bx, by = loc.get("x", 0), loc.get("y", 0)
        b = bm_data.get("bounds", {"width": 10, "height": 10})
        bw, bh = b["width"], b["height"]
        min_x = min(min_x, bx)
        min_y = min(min_y, by)
        max_x = max(max_x, bx + bw)
        max_y = max(max_y, by + bh)
        has_bitmaps = True
    if has_bitmaps:
        return {
            "frame_x1": int(min_x), "frame_y1": int(min_y),
            "frame_x2": int(max_x), "frame_y2": int(max_y),
            "frame_w": int(max_x - min_x), "frame_h": int(max_y - min_y),
        }
    return {"frame_x1": 0, "frame_y1": 0, "frame_x2": 0, "frame_y2": 0,
            "frame_w": 0, "frame_h": 0}


def _design_viewport(screen) -> dict | None:
    if not hasattr(screen, 'offset_x'):
        return None
    ox = screen.offset_x
    oy = screen.offset_y
    vp = getattr(screen, 'viewport', None)
    if vp is not None:
        vw, vh = vp[0], vp[1]
    else:
        vw = getattr(screen, 'viewport_w', 0)
        vh = getattr(screen, 'viewport_h', 0)
    bw = getattr(screen, 'width', 0)
    bh = getattr(screen, 'height', 0)
    return {
        "x1": ox, "y1": oy,
        "x2": min(ox + vw, bw), "y2": min(oy + vh, bh),
        "total_w": bw, "total_h": bh,
        "vp_w": vw, "vp_h": vh,
        "fits": vw >= bw and vh >= bh,
    }


def _map_viewport(screen, frame) -> dict | None:
    if not hasattr(screen, 'zoom_scale'):
        return None
    cw, ch = screen.compute_canvas_size()
    zoom = screen.zoom_scale
    aspect = screen.aspect_y
    px, py = screen.pan_x, screen.pan_y

    x1 = math.floor((0 - px) / zoom)
    y1 = math.floor((0 - py) / (zoom * aspect))
    x2 = math.ceil((cw - 1 - px) / zoom)
    y2 = math.ceil((ch - 1 - py) / (zoom * aspect))

    fits = (x1 <= frame["frame_x1"] and y1 <= frame["frame_y1"]
            and x2 >= frame["frame_x2"] and y2 >= frame["frame_y2"])
    return {
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "total_w": frame["frame_w"], "total_h": frame["frame_h"],
        "vp_w": cw, "vp_h": ch,
        "fits": fits,
    }


def _history_info(app, current_key: str) -> dict:
    undo = app.history.get_undo(current_key)
    redo = app.history.get_redo(current_key)
    return {"undo_depth": len(undo), "redo_depth": len(redo)}


def _mode_info(screen, app) -> dict:
    return {
        "cursor": (getattr(screen, 'cursor_x', None), getattr(screen, 'cursor_y', None)),
        "color": app.current_color,
        "zoom": getattr(screen, 'zoom_scale', None),
    }


def gather_info(app, screen) -> dict:
    current_key = (
        getattr(screen, '_key_on_enter', None)
        or getattr(screen, 'selected_key', None)
        or app.current_key
    )
    data = {}
    data.update(_file_info(app))
    data["total_keys"] = len(app.bitmaps)
    data.update(_current_key_info(app, current_key))
    data.update(_pixel_counts(app))
    data.update(_canvas_frame(app))
    data["design_viewport"] = _design_viewport(screen)
    data["map_viewport"] = _map_viewport(screen, data)
    data.update(_history_info(app, current_key))
    data.update(_mode_info(screen, app))
    return data


def _info_text(data: dict) -> str:
    lines = []

    file_part = data["filename"]
    if data["filesize"] is not None:
        file_part += f"  ({_format_size(data['filesize'])})"
    if data["dirty"]:
        file_part += "  [accent]modified[/]"
    lines.append(f"[bold]File:[/] {file_part}")

    lines.append(
        f"[bold]Keys:[/] {data['total_keys']}"
        f"  |  [bold]Pixel area:[/] {data['total_pixel_area']} cells"
        f"  |  [bold]Filled:[/] {data['total_filled']} cells"
    )

    lines.append(
        f"[bold]Canvas:[/] {data['frame_w']}×{data['frame_h']}"
        f" = {data['frame_w'] * data['frame_h']} cells"
    )

    vp = data.get("design_viewport") or data.get("map_viewport")
    if vp:
        if vp["fits"]:
            lines.append(f"[bold]Viewport:[/] fits  viewport {vp['vp_w']}×{vp['vp_h']}")
        else:
            lines.append(
                f"[bold]Viewport:[/] ({vp['x1']},{vp['y1']})→({vp['x2']},{vp['y2']})"
                f"  viewport {vp['vp_w']}×{vp['vp_h']}"
                f"  canvas {vp['total_w']}×{vp['total_h']}"
            )

    lines.append("")

    kw, kh = data["key_bounds"]
    kx, ky = data["key_location"]
    lines.append(
        f"[bold]Key:[/] \"{data['current_key']}\""
        f"  |  [bold]Bounds:[/] {kw}×{kh}"
        f"  |  [bold]Location:[/] ({kx},{ky})"
    )

    kt = data["key_total"]
    kf = data["key_filled"]
    if kt > 0:
        pct = kf / kt * 100
        lines.append(
            f"[bold]Filled:[/] {kf} / {kt}  ({pct:.1f}%)"
            f"  |  [bold]Undo:[/] {data['undo_depth']}"
            f"  |  [bold]Redo:[/] {data['redo_depth']}"
        )
    else:
        lines.append(f"[bold]Undo:[/] {data['undo_depth']}  |  [bold]Redo:[/] {data['redo_depth']}")

    cx, cy = data["cursor"]
    if cx is not None:
        lines.append(f"[bold]Cursor:[/] ({cx},{cy})  |  [bold]Color:[/] {data['color']}")

    zoom = data.get("zoom")
    if zoom is not None:
        lines.append(f"[bold]Zoom:[/] {int(zoom * 100)}%")

    return "\n".join(lines)


class InfoScreen(PopupScreen):
    """Popup showing metadata about the current bitmap project."""
    base_title = "Info"

    def __init__(self, data: dict, app, screen):
        super().__init__()
        self.info_data = data
        self._app = app
        self._screen = screen

    def _refresh(self):
        self.info_data = gather_info(self._app, self._screen)
        self.query_one("#content", Static).update(_info_text(self.info_data))

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(_info_text(self.info_data), id="content")
            yield Static("[wasd] switch key  [Escape] close", id="hints", markup=False)
            yield Static("", id="status")

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        k = event.key.lower()
        if k in ("w", "a", "s", "d"):
            dirs = {"d": "right", "a": "left", "s": "down", "w": "up"}
            dest = self._app.navigate_key(dirs[k], self.info_data["current_key"])
            if dest:
                self._app.set_current_key(dest)
                scr = self._screen
                if hasattr(scr, 'switch_to_key'):
                    scr.switch_to_key(dest)
                elif hasattr(scr, 'selected_key'):
                    scr.selected_key = dest
                    if hasattr(scr, 'refresh_map'):
                        scr.refresh_map()
                self._refresh()
                self.query_one("#status", Static).update(f"Switched to key {dest}")
            else:
                msgs = {"right": "No key right", "left": "No key left",
                        "down": "No key below", "up": "No key above"}
                self.query_one("#status", Static).update(msgs[dirs[k]])
            return
        if event.key in ("escape", "enter", "\n"):
            self.app.pop_screen()
