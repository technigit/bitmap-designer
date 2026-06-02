"""Code generation and generic response screens."""
from __future__ import annotations
from typing import TYPE_CHECKING
import pyperclip

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Vertical, VerticalScroll

from ..codegen_service import CodegenService
from .popup_screen import PopupScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class CodegenScreen(PopupScreen):
    """Screen to display and copy generated JavaScript code."""
    CSS = """
    #code-outer { max-height: 60vh; }
    VerticalScroll { max-height: 50vh; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="code-outer"):
            yield Static(self.app.title_with_file("Code Generation"), id="title")
            yield VerticalScroll(Static("", id="code"))
            yield Static("[Enter] copy  [Escape] close", id="hints", markup=False)
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_mount(self) -> None:
        code = CodegenService(self.app.bitmaps, palette=self.app.active_palette).generate_code()
        self.query_one("#code").update(code or "No bitmap data.")

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.refresh(repaint=True, layout=True)
            return
        if event.key in ("enter", "\n"):
            code = CodegenService(self.app.bitmaps, palette=self.app.active_palette).generate_code()
            pyperclip.copy(code)
            self.show_status("Code copied to clipboard.")
        elif event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("j", "down"):
            event.stop()
            self.query_one(VerticalScroll).scroll_down()
        elif event.key in ("k", "up"):
            event.stop()
            self.query_one(VerticalScroll).scroll_up()


class ResponseScreen(Screen):
    """Generic message screen with an OK button."""

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Static("Message", id="title")
        with Vertical():
            yield Static(self.message, id="message")
            yield Button("OK", id="ok")

    def on_button_pressed(self, event) -> None:
        if event.button.id == "ok":
            self.app.pop_screen()

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.app.pop_screen()
