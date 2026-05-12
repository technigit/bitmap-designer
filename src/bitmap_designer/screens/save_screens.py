"""Save screens for main, quit, and close flows."""
from __future__ import annotations
import os
import json
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input
from textual.widgets._input import Selection
from textual.containers import Vertical

from ..constants import DEFAULT_BITMAP_DIR

from .startup_screens import StartupScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class SaveScreen(Screen):
    """Screen to save the current bitmap file."""
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.filename = "Untitled"
        self.filename_input = None

    def compose(self) -> ComposeResult:
        yield Static("Save File", id="title")
        with Vertical():
            yield Static(f"Directory: {DEFAULT_BITMAP_DIR}", id="dir")
            self.filename_input = Input(value=self.filename, placeholder="Filename", id="filename")
            yield self.filename_input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)

    def on_mount(self) -> None:
        if self.app.current_file:
            basename = os.path.basename(self.app.current_file)
            self.filename_input.value = basename
            if basename.endswith(".json"):
                self.filename_input.selection = Selection(0, len(basename) - 5)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.save_file()

    # Save all bitmaps to a JSON file.
    def save_file(self):
        filename = self.filename_input.value or "Untitled"
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)

        if not os.path.exists(DEFAULT_BITMAP_DIR):
            os.makedirs(DEFAULT_BITMAP_DIR, exist_ok=True)

        data = {
            "version": "1.0",
            "bitmaps": self.app.bitmaps,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.app.set_current_file(filepath)
            self.app.mark_dirty(False)
            self.app.show_status("File saved.")
            self.app.pop_screen()
        except (OSError, json.JSONDecodeError) as e:
            self.app.show_status(f"Error: {e}")


class QuitSaveScreen(Screen):
    """Save dialog shown during the quit flow."""
    CSS = """
    Input { margin: 1 0; }
    #hints { opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.filename = "Untitled"
        self.filename_input = None

    def compose(self) -> ComposeResult:
        yield Static("Save File", id="title")
        with Vertical():
            yield Static(f"Directory: {DEFAULT_BITMAP_DIR}", id="dir")
            self.filename_input = Input(value=self.filename, placeholder="Filename", id="filename")
            yield self.filename_input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)

    def on_mount(self) -> None:
        if self.app.current_file:
            basename = os.path.basename(self.app.current_file)
            self.filename_input.value = basename
            if basename.endswith(".json"):
                self.filename_input.selection = Selection(0, len(basename) - 5)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.save_file()

    # Save all bitmaps to a JSON file and exit.
    def save_file(self):
        filename = self.filename_input.value or "Untitled"
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)

        if not os.path.exists(DEFAULT_BITMAP_DIR):
            os.makedirs(DEFAULT_BITMAP_DIR, exist_ok=True)

        data = {
            "version": "1.0",
            "bitmaps": self.app.bitmaps,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.app.set_current_file(filepath)
            self.app.mark_dirty(False)
            self.app.exit()
        except (OSError, json.JSONDecodeError) as e:
            self.app.show_status(f"Error: {e}")


class SaveScreenForClose(Screen):
    """Save dialog shown when closing a file."""
    CSS = """
    Input { margin: 1 0; }
    #hints { opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.filename = "Untitled"
        self.filename_input = None

    def compose(self) -> ComposeResult:
        yield Static("Save File", id="title")
        with Vertical():
            yield Static(f"Directory: {DEFAULT_BITMAP_DIR}", id="dir")
            self.filename_input = Input(value=self.filename, placeholder="Filename", id="filename")
            yield self.filename_input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)

    def on_mount(self) -> None:
        if self.app.current_file:
            basename = os.path.basename(self.app.current_file)
            self.filename_input.value = basename
            if basename.endswith(".json"):
                self.filename_input.selection = Selection(0, len(basename) - 5)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.save_file()

    # Save all bitmaps to a JSON file and return to startup.
    def save_file(self):
        filename = self.filename_input.value or "Untitled"
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)

        if not os.path.exists(DEFAULT_BITMAP_DIR):
            os.makedirs(DEFAULT_BITMAP_DIR, exist_ok=True)

        data = {
            "version": "1.0",
            "bitmaps": self.app.bitmaps,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.app.set_current_file(filepath)
            self.app.mark_dirty(False)
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        except (OSError, json.JSONDecodeError) as e:
            self.app.show_status(f"Error: {e}")
