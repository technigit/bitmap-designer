"""Main application class and entry point."""
import copy
import json
import os
from textual.app import App, ComposeResult
from textual.widgets import Footer, Static
from textual.binding import Binding

from .constants import DEFAULT_BITMAP_DIR, create_default_bitmap
from .services.file_service import FileService
from .services.history_service import HistoryService
from .services.palette_service import resolve_palette, resolve_palette_with_status
from .screens import StartupScreen, MainScreen, QuitScreen


class BitmapDesignerApp(App):  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Textual App subclass orchestrating all screens and application state."""
    CSS = """
    #title { text-align: center; text-style: bold; margin-top: 1; margin-bottom: 2; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { color: $accent; }
    Vertical { margin-left: 3; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),

    ]

    def __init__(self):
        super().__init__()
        self.file = FileService()
        self.history = HistoryService()
        self.bitmaps = {}
        self.current_key = "1"
        self.current_color = "1"
        self.dirty = False
        self._clean_snapshot = None
        self._key_adjacency: dict[str, dict[str, str | None]] = {}
        self.cursor_positions: dict[str, tuple[int, int]] = {}
        self.scroll_offsets: dict[str, tuple[int, int]] = {}
        self.map_zoom: float | None = None
        self.map_pan: tuple[int, int] = (0, 0)
        self.map_pan_flip: bool = False
        self.step: int = 1
        self.cursor_timeout: int = 3  # seconds; 0 = disabled
        self.color_pixels: str = "on"
        self.glyphmode: bool = False
        self.palette_id: str | None = None
        self.custom_palettes: dict[str, dict] = {}
        self.active_palette: dict[str, dict] = self._init_palette()

    def _init_palette(self) -> dict[str, dict]:
        return resolve_palette(self.palette_id, self.custom_palettes or None)

    def _init_palette_from_data(self, data: dict) -> None:
        self.palette_id = data.get("palette")
        self.custom_palettes = data.get("palettes", {})
        resolved, status = resolve_palette_with_status(
            self.palette_id, self.custom_palettes or None
        )
        self.active_palette = resolved
        if status:
            self.show_status(status)

    @staticmethod
    def get_location(bitmap_data: dict) -> tuple[int, int]:
        loc = bitmap_data.get("location", {})
        return loc.get("x", 0), loc.get("y", 0)

    @staticmethod
    def rects_overlap(a_loc: tuple[int, int], a_bounds: dict,
                       b_loc: tuple[int, int], b_bounds: dict) -> bool:
        ax1, ay1 = a_loc
        ax2 = ax1 + a_bounds["width"]
        ay2 = ay1 + a_bounds["height"]
        bx1, by1 = b_loc
        bx2 = bx1 + b_bounds["width"]
        by2 = by1 + b_bounds["height"]
        return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

    def build_key_adjacency(self) -> None:
        adj = {}
        locs = {k: self.get_location(self.bitmaps[k]) for k in self.bitmaps}
        for key, (bx, by) in locs.items():
            best = {"left": None, "right": None, "up": None, "down": None}
            best_dist = {"left": None, "right": None, "up": None, "down": None}
            best_tie = {"left": None, "right": None, "up": None, "down": None}
            for ok, (ox, oy) in locs.items():
                if ok == key:
                    continue
                dx = ox - bx
                dy = oy - by
                dsq = dx * dx + dy * dy
                if dx > 0 and (best_dist["right"] is None or dsq < best_dist["right"]
                               or (dsq == best_dist["right"] and oy < best_tie["right"])):
                    best["right"] = ok
                    best_dist["right"] = dsq
                    best_tie["right"] = oy
                if dx < 0 and (best_dist["left"] is None or dsq < best_dist["left"]
                               or (dsq == best_dist["left"] and oy < best_tie["left"])):
                    best["left"] = ok
                    best_dist["left"] = dsq
                    best_tie["left"] = oy
                if dy > 0 and (best_dist["down"] is None or dsq < best_dist["down"]
                               or (dsq == best_dist["down"] and ox < best_tie["down"])):
                    best["down"] = ok
                    best_dist["down"] = dsq
                    best_tie["down"] = ox
                if dy < 0 and (best_dist["up"] is None or dsq < best_dist["up"]
                               or (dsq == best_dist["up"] and ox < best_tie["up"])):
                    best["up"] = ok
                    best_dist["up"] = dsq
                    best_tie["up"] = ox
            adj[key] = best
        self._key_adjacency = adj

    def navigate_key(self, direction: str, key: str | None = None) -> str | None:
        src = key if key is not None else self.current_key
        return self._key_adjacency.get(src, {}).get(direction)

    def _take_clean_snapshot(self) -> None:
        self._clean_snapshot = (
            copy.deepcopy(self.bitmaps),
            self.palette_id,
            copy.deepcopy(self.custom_palettes),
        )

    def _is_modified(self) -> bool:
        if self.history.any_nonempty():
            return True
        if self._clean_snapshot is not None:
            snap_bitmaps, snap_pid, snap_customs = self._clean_snapshot
            if self.bitmaps != snap_bitmaps:
                return True
            if self.palette_id != snap_pid:
                return True
            if self.custom_palettes != snap_customs:
                return True
        return False

    def mark_dirty(self, value: bool = True) -> None:
        if value is True:
            self.dirty = self._is_modified()
        else:
            self.dirty = False
            self._take_clean_snapshot()
        self._refresh_current_title()

    def _refresh_current_title(self):
        try:
            screen = self.screen
            title = screen.query_one("#title", Static)
            if hasattr(screen, 'base_title'):
                title.update(self.title_with_file(screen.base_title))
        except Exception:  # pylint: disable=W0718
            pass

    def title_with_file(self, base_title: str) -> str:
        if self.file.current_file:
            result = f"{base_title} - {self.file.basename}"
            if self.dirty:
                result += " (modified)"
            return result
        return base_title

    def set_bitmaps(self, bitmaps: dict) -> None:
        self.bitmaps = bitmaps
        self.build_key_adjacency()

    def set_current_key(self, key: str) -> None:
        self.current_key = key

    def reload_file(self) -> None:
        if not self.file.current_file or not os.path.exists(self.file.current_file):
            return
        try:
            with open(self.file.current_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                self.build_key_adjacency()
                if self.bitmaps:
                    self.current_key = next(iter(self.bitmaps.keys()))
                self.dirty = False
                self._take_clean_snapshot()
                self.history.clear_all()
                self.cursor_positions = {}
                self.scroll_offsets = {}
                self._init_palette_from_data(data)
                self.file.refresh_mtime()
        except (OSError, json.JSONDecodeError) as e:
            self.show_status(f"Error reloading file: {e}")

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(StartupScreen())

    async def action_quit(self) -> None:
        self.push_screen(QuitScreen())

    # Show a status message on the current screen's #status widget.

    def show_status(self, message: str) -> None:
        try:
            screen = self.screen
            if hasattr(screen, 'show_status'):
                screen.show_status(message)
        except Exception:  # pylint: disable=W0718
            pass

    # Create a new blank bitmap and open the main menu.

    def new_bitmap(self):
        self.bitmaps = {}
        self.current_key = "1"
        self.bitmaps["1"] = create_default_bitmap()
        self.build_key_adjacency()
        path = os.path.join(DEFAULT_BITMAP_DIR, "Untitled.json")
        if os.path.exists(path):
            n = 1
            while os.path.exists(
                os.path.join(DEFAULT_BITMAP_DIR, f"Untitled ({n}).json")
            ):
                n += 1
            path = os.path.join(DEFAULT_BITMAP_DIR, f"Untitled ({n}).json")
        self.file.set_current_file(path)
        self.dirty = False
        self._take_clean_snapshot()
        self.current_color = "1"
        self.history.clear_all()
        self.cursor_positions = {}
        self.scroll_offsets = {}
        self.step = 1
        self.color_pixels = "on"
        self.glyphmode = False
        self.palette_id = None
        self.custom_palettes = {}
        self.active_palette = self._init_palette()
        self.push_screen(MainScreen())

    # Load bitmaps from a JSON file and open the main menu.

    def load_file(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                self.build_key_adjacency()
                self.file.set_current_file(filepath)
                if self.bitmaps:
                    self.current_key = next(iter(self.bitmaps.keys()))
                self.dirty = False
                self._take_clean_snapshot()
                self.history.clear_all()
                self.cursor_positions = {}
                self.scroll_offsets = {}
                self.step = 1
                self.color_pixels = "on"
                self.glyphmode = False
                self._init_palette_from_data(data)
                self.push_screen(MainScreen())
        except (OSError, json.JSONDecodeError) as e:
            self.show_status(f"Error loading file: {e}")

    def find_empty_location(self, width: int = 10, height: int = 10) -> dict:
        """Find an unoccupied (x, y) position for a bitmap of given size."""
        step = 12
        occupied: set[tuple[int, int]] = set()
        for bm in self.bitmaps.values():
            loc = self.get_location(bm)
            bounds = bm.get("bounds", {"width": 10, "height": 10})
            for dx in range(bounds["width"]):
                for dy in range(bounds["height"]):
                    occupied.add((loc[0] + dx, loc[1] + dy))
        x, y = 0, 0
        while any(
            (x + dx, y + dy) in occupied
            for dx in range(width) for dy in range(height)
        ):
            x += step
            if x > 200:
                x = 0
                y += step
        return {"x": x, "y": y}

    def resolve_collisions(self, changed_key: str) -> list[str]:
        """Move any bitmaps encroached by changed_key's new bounds/location.
        Returns list of keys that were moved."""
        changed = self.bitmaps.get(changed_key)
        if not changed:
            return []
        changed_loc = self.get_location(changed)
        changed_bounds = changed["bounds"]
        moved = []
        for key in list(self.bitmaps.keys()):
            if key == changed_key:
                continue
            bm = self.bitmaps[key]
            loc = self.get_location(bm)
            b_bounds = bm["bounds"]
            if self.rects_overlap(changed_loc, changed_bounds, loc, b_bounds):
                del self.bitmaps[key]
                new_loc = self.find_empty_location(
                    width=b_bounds["width"], height=b_bounds["height"]
                )
                self.bitmaps[key] = bm
                bm["location"] = new_loc
                moved.append(key)
        if moved:
            self.build_key_adjacency()
        return moved

    def set_current_color(self, color: str):
        self.current_color = color

    def set_palette(self, palette_id: str | None, show_status_msg: bool = True) -> None:
        self.palette_id = palette_id
        resolved, status = resolve_palette_with_status(
            palette_id, self.custom_palettes or None
        )
        self.active_palette = resolved
        self.mark_dirty()
        if status and show_status_msg:
            self.show_status(status)

    def set_custom_palettes(self, palettes: dict[str, dict]) -> None:
        self.custom_palettes = palettes
        resolved, status = resolve_palette_with_status(
            self.palette_id, self.custom_palettes or None
        )
        self.active_palette = resolved
        self.mark_dirty()
        if status:
            self.show_status(status)


def run():
    """Run the bitmap designer application."""
    app = BitmapDesignerApp()
    app.run()


if __name__ == "__main__":
    run()
