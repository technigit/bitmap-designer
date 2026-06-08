"""Quit flow screens."""
from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Vertical

from .popup_screen import PopupScreen

from .save_screen import QuitSaveScreen, SaveFirstScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class QuitScreen(PopupScreen):
    """Initial quit confirmation screen."""

    def on_mount(self) -> None:
        if not self.app.dirty:
            self.app.exit()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Quit", id="title")
            yield Static("Really quit? (y/N)", id="prompt")
            yield Static(
                "[!] force quit (without saving)  [Escape] cancel",
                id="hints", markup=False
            )

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(QuitSaveFileFirstScreen())
        elif event.key in ("!", "exclamation_mark", "shift+1"):
            self.app.exit()
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()


class QuitSaveFileFirstScreen(SaveFirstScreen):
    """Screen asking whether to save before quitting."""
    TITLE = "Quit - Save"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.TITLE, id="title")
            yield Static("Save file first? (Y/n)", id="prompt")
            yield Static(
                "[!] force quit (without saving)  [Escape] cancel",
                id="hints", markup=False
            )

    def on_key(self, event):
        if event.key in ("!", "exclamation_mark", "shift+1"):
            self.app.exit()
        else:
            super().on_key(event)

    def _on_yes(self):
        self.app.push_screen(QuitSaveScreen())

    def _on_no(self):
        self.app.exit()

    def _on_escape(self):
        self.app.pop_screen()
