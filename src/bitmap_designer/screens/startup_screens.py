"""Startup and file-open screens."""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from ..constants import ASCII_HEADER, DEFAULT_BITMAP_DIR

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class StartupScreen(Screen):
    """Startup screen with New/Open/Quit menu."""
    CSS = """
    #menu { margin-top: 1; }
    """
    def compose(self) -> ComposeResult:
        yield Static(ASCII_HEADER, markup=False, id="title")
        with Vertical():
            yield Static("[N]ew Bitmap  [O]pen Bitmap  [Q]uit", id="menu", markup=False)

    def on_mount(self) -> None:
        self.app.title = "Bitmap Designer"

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "q":
            self.app.action_quit()
        elif key == "n":
            self.app.new_bitmap()
        elif key == "o":
            self.app.push_screen(OpenScreen())


class OpenScreen(Screen):
    """Screen to list and open .json bitmap files."""
    CSS = """
    #file_list { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    """
    def __init__(self):
        super().__init__()
        self.files = []
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        yield Static("Open Bitmap", id="title")
        with Vertical():
            yield Static("", id="file_list")
            yield Static("[Enter] Open  [Escape] Back", id="hints", markup=False)

    def on_mount(self) -> None:
        self.refresh_files()

    # Scan the bitmap directory and update the file list.

    def refresh_files(self):
        if not os.path.exists(DEFAULT_BITMAP_DIR):
            self.query_one("#file_list").update(
                "No .json files found.\nCreate ~/bitmaps directory first."
            )
            return

        self.files = sorted([f for f in os.listdir(DEFAULT_BITMAP_DIR) if f.endswith(".json")])

        if self.files:
            self.selected_idx = 0
            self._update_list()
        else:
            self.query_one("#file_list").update("No .json files found.")

    def _update_list(self):
        lines = []
        for i, f in enumerate(self.files):
            marker = ">" if i == self.selected_idx else " "
            lines.append(f"{marker} {f}")
        self.query_one("#file_list").update("\n".join(lines))

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            if self.files:
                self.open_file()
        elif event.key in ("up", "k") and self.files:
            self.selected_idx = (self.selected_idx - 1) % len(self.files)
            self._update_list()
        elif event.key in ("down", "j") and self.files:
            self.selected_idx = (self.selected_idx + 1) % len(self.files)
            self._update_list()

    # Load the selected file from the list.

    def open_file(self):
        filename = self.files[self.selected_idx]
        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)
        self.app.load_file(filepath)
