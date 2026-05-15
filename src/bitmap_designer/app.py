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

    def set_current_key(self, key: str) -> None:
        self.current_key = key

    def reload_file(self) -> None:
        if not self.file.current_file or not os.path.exists(self.file.current_file):
            return
        try:
            with open(self.file.current_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                if self.bitmaps:
                    self.current_key = next(iter(self.bitmaps.keys()))
                self.dirty = False
                self._take_clean_snapshot()
                self.history.clear_all()
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
        self.file.set_current_file(os.path.join(DEFAULT_BITMAP_DIR, "Untitled.json"))
        self.dirty = False
        self._take_clean_snapshot()
        self.current_color = "1"
        self.history.clear_all()
        self.push_screen(MainScreen())

    # Load bitmaps from a JSON file and open the main menu.

    def load_file(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                self.file.set_current_file(filepath)
                if self.bitmaps:
                    self.current_key = next(iter(self.bitmaps.keys()))
                self.dirty = False
                self._take_clean_snapshot()
                self.history.clear_all()
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
