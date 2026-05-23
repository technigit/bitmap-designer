"""Startup and file-open screens."""
from __future__ import annotations
import os
import re
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import ListItem, ListView, Static
from textual.containers import Vertical

from .popup_screen import PopupScreen

from ..constants import ASCII_HEADER, DEFAULT_BITMAP_DIR

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


def _natural_key(s: str) -> list:
    """Split string into text/number parts for human-friendly sorting."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


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
        self.app.set_current_color("1")

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        key = event.key.lower()
        if key == "n":
            self.app.new_bitmap()
        elif key == "o":
            self.app.push_screen(OpenScreen())


class OpenScreen(PopupScreen):
    """Screen to list and open .json bitmap files."""
    CSS = """
    #open-screen-vertical { max-height: 60vh; }
    #file_list { max-height: 50vh; }
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.files: list[tuple[str, bool]] = []
        self.current_dir = DEFAULT_BITMAP_DIR
        self._prev_selected: dict[str, str] = {}

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def compose(self) -> ComposeResult:
        with Vertical(id="open-screen-vertical"):
            yield Static("Open Bitmap", id="title")
            yield ListView(id="file_list")
            yield Static("[Enter] Open  [Escape] Back", id="hints", markup=False)
            yield Static("", id="status")

    async def on_mount(self) -> None:
        await self.refresh_files()

    async def refresh_files(self):
        if not os.path.exists(self.current_dir):
            msg = "Create ~/bitmaps directory first." \
                if self.current_dir == DEFAULT_BITMAP_DIR \
                else f"Directory not found: {self.current_dir}"
            list_view = self.query_one("#file_list", ListView)
            await list_view.clear()
            await list_view.append(ListItem(Static(msg)))
            return

        entries = os.listdir(self.current_dir)
        self.files = []
        for entry in entries:
            path = os.path.join(self.current_dir, entry)
            if os.path.isdir(path) or entry.endswith(".json"):
                self.files.append((entry, os.path.isdir(path)))
        self.files.sort(key=lambda e: _natural_key(e[0]))
        self.files.sort(key=lambda e: os.path.getmtime(os.path.join(self.current_dir, e[0])),
                        reverse=True)
        self._update_title()
        await self._update_list()

    def _update_title(self):
        title = self.query_one("#title", Static)
        if self.current_dir != DEFAULT_BITMAP_DIR:
            basename = os.path.basename(self.current_dir)
            title.update(f"Open Bitmap \u2014 {basename}/")
        else:
            title.update("Open Bitmap")

    async def _update_list(self):
        list_view = self.query_one("#file_list", ListView)
        await list_view.clear()
        items: list[ListItem] = []
        if self.current_dir != DEFAULT_BITMAP_DIR:
            items.append(ListItem(Static(" ../")))
        if not self.files:
            items.append(ListItem(Static("No .json files found."), disabled=True))
        else:
            for name, is_folder in self.files:
                label = f" {name}/" if is_folder else f" {name}"
                items.append(ListItem(Static(label)))
        await list_view.extend(items)
        prev = self._prev_selected.get(self.current_dir)
        if prev:
            offset = 1 if self.current_dir != DEFAULT_BITMAP_DIR else 0
            for i, (name, _) in enumerate(self.files):
                if name == prev:
                    list_view.index = i + offset
                    break
            else:
                list_view.index = 0
        else:
            list_view.index = 0
        list_view.focus()

    async def on_list_view_selected(self, _event: ListView.Selected) -> None:
        list_view = self.query_one("#file_list", ListView)
        idx = list_view.index
        if idx is None:
            return
        offset = 1 if self.current_dir != DEFAULT_BITMAP_DIR else 0
        if offset and idx == 0:
            self.current_dir = os.path.dirname(self.current_dir)
            await self.refresh_files()
            return
        if not self.files:
            return
        file_idx = idx - offset
        if 0 <= file_idx < len(self.files):
            name, is_folder = self.files[file_idx]
            if is_folder:
                self._prev_selected[self.current_dir] = name
                self.current_dir = os.path.join(self.current_dir, name)
                await self.refresh_files()
            else:
                self._open_file(name)

    def _open_file(self, filename: str):
        filepath = os.path.join(self.current_dir, filename)
        self.app.load_file(filepath)

    async def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            if self.current_dir != DEFAULT_BITMAP_DIR:
                self.current_dir = os.path.dirname(self.current_dir)
                await self.refresh_files()
            else:
                self.app.pop_screen()
            return
        if event.key in ("j", "down"):
            self.query_one("#file_list", ListView).action_cursor_down()
        elif event.key in ("k", "up"):
            self.query_one("#file_list", ListView).action_cursor_up()
