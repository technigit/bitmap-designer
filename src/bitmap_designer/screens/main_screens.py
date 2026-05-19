"""Main menu and close flow screens."""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from .popup_screen import PopupScreen

from .startup_screens import StartupScreen
from .design_screens import DesignScreen
from .save_screens import SaveFirstScreen, SaveScreen, SaveScreenForClose
from .manage_screens import ManageScreen
from .config_screens import ConfigScreen
from .codegen_screens import CodegenScreen

from ..codegen_service import CodegenService

from ..constants import HINT_ESCAPE, create_default_bitmap

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class MainScreen(Screen):
    """Main menu screen hub linking to design, preview, save, codegen, and config."""
    base_title = "Main Menu"
    TITLE = "Main Menu"
    CSS = """
    #status { margin-left: 3; }
    """

    def _menu_text(self) -> str:
        return (
            "[D]esign mode\n"
            "[P]review\n"
            "[G]enerate code\n"
            "\n"
            "[S]ave file\n"
            "[M]anage file\n"
            "[,] Configuration\n"
            "[Escape] back"
        )

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self.TITLE), id="title")
        with Vertical():
            yield Static(self._menu_text(), id="menu", markup=False)
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_screen_resume(self, _event) -> None:
        title = self.query_one("#title", Static)
        title.update(self.app.title_with_file(self.TITLE))
        menu = self.query_one("#menu", Static)
        menu.update(self._menu_text())
        if self.app.file.check_external_change() and self.app.file.current_file:
            self.app.push_screen(FileChangedScreen(self.app.file.current_file))

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        key = event.key
        if key == "comma":
            self.app.push_screen(ConfigScreen())
            return
        key_lower = key.lower()
        if key_lower == "d":
            bitmap = self.app.bitmaps.get(
                self.app.current_key,
                create_default_bitmap()
            )
            self.app.push_screen(DesignScreen(bitmap))
        elif key_lower == "p":
            CodegenService(self.app.bitmaps, self.app.show_status).preview()
        elif key_lower == "s":
            self.app.push_screen(SaveScreen())
        elif key_lower == "g":
            self.app.push_screen(CodegenScreen())
        elif key_lower == "m":
            self.app.push_screen(ManageScreen())
        elif key == "escape":
            self.app.push_screen(CloseScreen())


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
            yield Static(HINT_ESCAPE, id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(SaveFileFirstScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()


class SaveFileFirstScreen(SaveFirstScreen):
    """Screen asking whether to save before closing."""
    TITLE = "Close - Save"

    def _on_yes(self):
        self.app.push_screen(SaveScreenForClose())

    def _on_no(self):
        self.app.pop_screen()
        self.app.push_screen(AreYouSureScreen())

    def _on_escape(self):
        self.app.pop_screen()
        self.app.push_screen(MainScreen())


class AreYouSureScreen(PopupScreen):
    """Final confirmation screen when discarding changes."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Close - Confirm", id="title")
            yield Static("Are you sure? (y/N)", id="prompt")
            yield Static(HINT_ESCAPE, id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key.lower() == "y":
            self.app.mark_dirty(False)
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()
            self.app.push_screen(MainScreen())


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
