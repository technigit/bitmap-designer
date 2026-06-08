"""Close flow confirmation screens."""
from __future__ import annotations
import os

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical

from .popup_screen import PopupScreen
from .startup_screen import StartupScreen
from .save_screen import SaveFirstScreen, SaveScreenForClose


class CloseScreen(PopupScreen):
    """Close confirmation screen from the main menu."""

    def on_mount(self) -> None:
        if not self.app.dirty:
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Close", id="title")
            yield Static("Really close? (y/N)", id="prompt")
            yield Static(
                "[!] force close (without saving)  [Escape] cancel",
                id="hints", markup=False
            )

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key in ("!", "exclamation_mark", "shift+1"):
            self.app.mark_dirty(False)
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        elif event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(SaveFileFirstScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()


class SaveFileFirstScreen(SaveFirstScreen):
    """Screen asking whether to save before closing."""
    TITLE = "Close - Save"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.TITLE, id="title")
            yield Static("Save file first? (Y/n)", id="prompt")
            yield Static(
                "[!] force close (without saving)  [Escape] cancel",
                id="hints", markup=False
            )

    def on_key(self, event):
        if event.key in ("!", "exclamation_mark", "shift+1"):
            self.app.mark_dirty(False)
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        else:
            super().on_key(event)

    def _on_yes(self):
        self.app.push_screen(SaveScreenForClose())

    def _on_no(self):
        self.app.pop_screen()
        self.app.push_screen(AreYouSureScreen())

    def _on_escape(self):
        self.app.pop_screen()
        self.app.pop_screen()


class AreYouSureScreen(PopupScreen):
    """Final confirmation screen when discarding changes."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Close - Confirm", id="title")
            yield Static("Are you sure? (y/N)", id="prompt")
            yield Static(
                "[!] force close (without saving)  [Escape] cancel",
                id="hints", markup=False
            )

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key in ("!", "exclamation_mark", "shift+1"):
            self.app.mark_dirty(False)
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        elif event.key.lower() == "y":
            self.app.mark_dirty(False)
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()
            self.app.pop_screen()


class FileChangedScreen(PopupScreen):
    """Warning screen when the file has been externally edited."""
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Warning", id="title")
            yield Static(
                f"File '{os.path.basename(self.filepath)}' has been externally edited.",
                id="warning"
            )
            yield Static("[O]K (ignore), [R]eload", id="hints", markup=False)
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        key = event.key.lower()
        if key in ("o", "enter", "\n"):
            self.app.refresh_mtime()
            self.app.pop_screen()
        elif key == "r":
            if self.app.dirty:
                self.show_status("Cannot reload: save your changes first.")
                return
            self.app.reload_file()
            self.app.pop_screen()
        elif key == "escape":
            self.app.pop_screen()
