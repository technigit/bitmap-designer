"""Quit flow screens."""
from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from ..constants import HINT_ESCAPE

from .save_screens import QuitSaveScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class QuitScreen(Screen):
    """Initial quit confirmation screen."""

    def on_mount(self) -> None:
        if not self.app.dirty:
            self.app.exit()

    def compose(self) -> ComposeResult:
        yield Static("Quit", id="title")
        with Vertical():
            yield Static("Really quit? (y/N)", id="prompt")
            yield Static(HINT_ESCAPE, id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(QuitSaveFileFirstScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()


class QuitSaveFileFirstScreen(Screen):
    """Screen asking whether to save before quitting."""

    def compose(self) -> ComposeResult:
        yield Static("Quit - Save", id="title")
        with Vertical():
            yield Static("Save file first? (Y/n)", id="prompt")
            yield Static(HINT_ESCAPE, id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key in ("enter", "\n") or event.key.lower() == "y":
            self.app.push_screen(QuitSaveScreen())
        elif event.key.lower() == "n":
            self.app.exit()
        elif event.key == "escape":
            self.app.pop_screen()
