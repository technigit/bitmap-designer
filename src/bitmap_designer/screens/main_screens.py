"""Main menu and close flow screens."""
from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Vertical

from .close_screens import CloseScreen, FileChangedScreen
from .design_screens import DesignScreen
from .save_screens import SaveScreen
from .manage_screens import ManageScreen
from .config_screens import ConfigScreen
from .codegen_screens import CodegenScreen

from ..codegen_service import CodegenService

from ..constants import create_default_bitmap

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
