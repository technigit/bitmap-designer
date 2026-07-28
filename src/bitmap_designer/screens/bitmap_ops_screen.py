"""Popup with key-level operations: New, Copy, Rename, Delete."""

from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from .popup_screen import PopupScreen

if TYPE_CHECKING:
    pass


class BitmapOpsScreen(PopupScreen):
    """Popup with key-level operations: New, Copy, Rename, Delete."""

    base_title = "Bitmap Operations"
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(
                "  [N]ew key\n"
                "  [C]opy (duplicate) current key\n"
                "  [R]ename current key\n"
                "  [D]elete current key\n",
                markup=False,
            )
            yield Static("[Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        k = event.key.lower()
        if k == "n":
            self.dismiss("n")
        elif k == "c":
            self.dismiss("c")
        elif k == "r":
            self.dismiss("r")
        elif k == "d":
            self.dismiss("d")
        elif event.key == "escape":
            self.dismiss(None)
