"""File management screens (rename, delete)."""
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


class ManageScreen(Screen):
    """Menu screen for file management operations."""
    CSS = """
    #menu { margin-top: 1; }
    #status { dock: bottom; }
    """

    TITLE = "Manage File"

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.TITLE), id="title")
        with Vertical():
            yield Static(
                "[R]ename file\n"
                "[D]elete file",
                id="menu",
                markup=False
            )
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_screen_resume(self, _event) -> None:
        self.query_one("#title", Static).update(self.app.title_with_file(self.TITLE))

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key.lower() == "r":
            self.app.push_screen(RenameScreen())
        elif event.key.lower() == "d":
            self.app.push_screen(DeleteScreen())
        elif event.key == "escape":
            self.app.pop_screen()


class RenameScreen(Screen):
    """Screen to rename the current file."""
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None
        self.current_file = None

    def compose(self) -> ComposeResult:
        current = os.path.basename(self.app.current_file or "Untitled.json")
        yield Static("Rename File", id="title")
        with Vertical():
            self.input = Input(
                value=current,
                placeholder="New filename",
                id="filename"
            )
            yield self.input
            yield Static("[Enter] rename  [Escape] cancel", id="hints")

    def on_mount(self) -> None:
        if self.input.value.endswith(".json"):
            self.input.selection = Selection(0, len(self.input.value) - 5)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.rename_file()

    # Rename the current file on disk.
    def rename_file(self):
        if not self.app.current_file:
            self.app.show_status("No file to rename.")
            return

        new_name = self.input.value or "Untitled"
        if not new_name.endswith(".json"):
            new_name += ".json"

        dir_path = DEFAULT_BITMAP_DIR
        new_path = os.path.join(dir_path, new_name)

        if os.path.exists(new_path):
            self.app.show_status("File already exists.")
            return

        try:
            os.rename(self.app.current_file, new_path)
            self.app.current_file = new_path
            self.app.show_status("File renamed.")
            self.app.pop_screen()
        except (OSError, json.JSONDecodeError) as e:
            self.app.show_status(f"Error: {e}")


class DeleteScreen(Screen):
    """Screen to confirm and delete the current file."""
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Delete File", id="title")
        with Vertical():
            yield Static("Are you sure you want to delete this file?", id="prompt")
            yield Static("[Y]es  [N]o", id="hints", markup=False)
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key.lower() == "y":
            self.delete_file()
        elif event.key.lower() in ("n", "escape"):
            self.app.pop_screen()

    # Delete the current file and reset application state.
    def delete_file(self):
        if not self.app.current_file or not os.path.exists(self.app.current_file):
            self.app.show_status("No file to delete.")
            return
        try:
            os.remove(self.app.current_file)
            self.app.set_current_file(None)
            self.app.set_bitmaps({})
            self.app.mark_dirty(False)
            self.app.show_status("File deleted.")
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        except (OSError, json.JSONDecodeError) as e:
            self.app.show_status(f"Error: {e}")
