"""Main application class and entry point."""
import copy
import json
import os
from textual.app import App, ComposeResult
from textual.widgets import Footer, Static
from textual.binding import Binding

from .constants import DEFAULT_BITMAP_DIR, create_default_bitmap
from .file_service import FileService
from .history_service import HistoryService
from .screens import StartupScreen, MainScreen, QuitScreen


class BitmapDesignerApp(App):
    """Textual App subclass orchestrating all screens and application state."""
    CSS = """
    #title { text-align: center; text-style: bold; margin-top: 1; margin-bottom: 2; }
    #hints { margin-top: 1; opacity: 0.5; }
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

    @staticmethod
    def _get_location(bitmap_data: dict) -> tuple[int, int]:
        loc = bitmap_data.get("location", {})
        return loc.get("x", 0), loc.get("y", 0)

    def build_key_adjacency(self) -> None:
        adj = {}
        locs = {k: self._get_location(self.bitmaps[k]) for k in self.bitmaps}
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

    def navigate_key(self, direction: str) -> str | None:
        return self._key_adjacency.get(self.current_key, {}).get(direction)

    def _take_clean_snapshot(self) -> None:
        self._clean_snapshot = copy.deepcopy(self.bitmaps)

    def _is_modified(self) -> bool:
        if self.history.any_nonempty():
            return True
        if self._clean_snapshot is not None and self.bitmaps != self._clean_snapshot:
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
        screen = self.screen
        title = screen.query_one("#title", Static)
        if hasattr(screen, 'base_title'):
            title.update(self.title_with_file(screen.base_title))

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
        self.file.set_current_file(os.path.join(DEFAULT_BITMAP_DIR, "Untitled.json"))
        self.dirty = False
        self._take_clean_snapshot()
        self.current_color = "1"
        self.history.clear_all()
        self.cursor_positions = {}
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
                self.push_screen(MainScreen())
        except (OSError, json.JSONDecodeError) as e:
            self.show_status(f"Error loading file: {e}")

    def set_current_color(self, color: str):
        self.current_color = color

def run():
    """Run the bitmap designer application."""
    app = BitmapDesignerApp()
    app.run()


if __name__ == "__main__":
    run()
