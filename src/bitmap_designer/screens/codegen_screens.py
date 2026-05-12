"""Code generation and generic response screens."""
from __future__ import annotations
from typing import TYPE_CHECKING
import pyperclip

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Vertical

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class CodegenScreen(Screen):
    """Screen to display and copy generated JavaScript code."""
    CSS = """
    #code { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Code Generation"), id="title")
        with Vertical():
            yield Static("", id="code")
            yield Static("[Enter] copy  [Escape] close", id="hints")

    def on_mount(self) -> None:
        code = self.app.generate_code()
        self.query_one("#code").update(code or "No bitmap data.")

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key in ("enter", "\n"):
            code = self.app.generate_code()
            pyperclip.copy(code)
            self.app.show_status("Code copied to clipboard.")
        elif event.key == "escape":
            self.app.pop_screen()


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
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.app.pop_screen()
