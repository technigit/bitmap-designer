"""Screens for placing new or duplicate bitmap keys."""

from __future__ import annotations
import copy
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.widgets import Input, Static
from textual.containers import Vertical

from .popup_screen import PopupScreen
from ..constants import create_default_bitmap

if TYPE_CHECKING:
    pass


class DirectionSelectScreen(PopupScreen):
    """Pop-up to choose a direction for placing a new/duplicate key."""

    base_title = "Place Key"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(
                "  [Q] Up-Left  [W] Up  [E] Up-Right\n"
                "  [A] Left           [D] Right\n"
                "  [Z] Down-Left [S] Down [X] Down-Right\n",
                markup=False,
            )
            yield Static("[Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        mapping = {
            "q": "up-left", "w": "up", "e": "up-right",
            "a": "left", "d": "right",
            "z": "down-left", "s": "down", "x": "down-right",
        }
        if event.key.lower() in mapping:
            self.dismiss(mapping[event.key.lower()])
        elif event.key == "escape":
            self.dismiss(None)


class NewKeyScreen(PopupScreen):
    """Pop-up to name a new or duplicated key, then create it."""

    base_title = "New Key"
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def __init__(self, direction: str, duplicate: bool, suggested_name: str, source_key: str):
        super().__init__()
        self.direction = direction
        self.duplicate = duplicate
        self.suggested_name = suggested_name
        self.source_key = source_key
        self.input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                self.app.title_with_file(
                    "Duplicate Key" if self.duplicate else "New Key"
                ),
                id="title",
            )
            self.input = Input(value=self.suggested_name, placeholder="Key name")
            yield self.input
            yield Static("[Enter] create  [Escape] cancel", id="hints", markup=False)
            yield Static("", id="status")

    def on_mount(self) -> None:
        if self.input:
            self.input.focus()
            self.input.action_select_all()

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self._create_key()

    def _create_key(self) -> None:
        name = (self.input.value or "").strip()
        if not name or " " in name:
            self.show_status("Please enter a valid key name (no spaces).")
            return
        if name in self.app.bitmaps:
            self.show_status(f"Key '{name}' already exists.")
            return
        w = self.app.bitmaps.get(self.source_key, {}).get("bounds", {}).get("width", 10)
        h = self.app.bitmaps.get(self.source_key, {}).get("bounds", {}).get("height", 10)
        loc = self.app.find_nearby_location(
            self.source_key, self.direction,
            w if self.duplicate else 10,
            h if self.duplicate else 10,
        )
        if loc is None:
            self.show_status("No space in that direction.")
            return
        if self.duplicate:
            src = self.app.bitmaps.get(self.source_key, create_default_bitmap())
            bm = copy.deepcopy(src)
            bm["location"] = loc
        else:
            bm = create_default_bitmap()
            bm["location"] = loc
        self.app.bitmaps[name] = bm
        self.app.build_key_adjacency()
        self.app.mark_dirty()
        self.app.set_current_key(name)
        self.app.pop_screen()
