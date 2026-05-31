"""Vim-style : command bar for Design and Map screens."""
from __future__ import annotations
import json
import os
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from .close_screens import CloseScreen
from .config_screens import ConfigScreen
from .info_screen import InfoScreen, gather_info
from .popup_screen import PopupScreen
from .quit_screens import QuitScreen
from .startup_screens import StartupScreen
from ..constants import DEFAULT_BITMAP_DIR, create_default_bitmap

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp

CMD_HELP_TEXT = """\
[bold]Command Bar[/bold]

:q       Quit (with confirmation if modified)
:q!      Force quit (discard changes)
:w       Save current file
:w <name> Save as a new file
:w!      Force save (overwrite external changes)
:w! <name> Force save and overwrite existing
:wq      Save and quit
:e       Exit to previous screen
:close   Close project (with confirmation if modified)
:close!  Force close (discard changes)
:help    Show this help
:scroll  Enable scroll mode (Design mode only)
:noscroll Disable scroll mode (Design mode only)
:pan     Enable pan mode (Map mode only)
:nopan   Disable pan mode (Map mode only)
:set step N       Set cursor/scroll step (1-9)
:set key NAME     Switch to or create a bitmap key
:set color C      Set current drawing color (0-9, A-F)
:set colorpixels [on|off|mixed]  Set pixel display mode
:info          Show project metadata
:config        Open the configuration menu
:config key NAME  Switch to key and open config\
"""


class HelpPopupScreen(PopupScreen):
    """Popup showing command bar keybinding reference."""
    base_title = "Command Help"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(CMD_HELP_TEXT, id="content")
            yield Static("[Escape] close", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.app.pop_screen()


def handle_cmd_key(screen, event) -> bool:
    """Handle a key event for command mode. Returns True if consumed."""
    key = event.key

    if not getattr(screen, 'cmd_mode', False) and key in ("colon", "shift+semicolon"):
        screen.cmd_mode = True
        screen.cmd_buffer = ""
        screen.show_status(":")
        return True

    if not screen.cmd_mode:
        return False

    if key == "escape":
        screen.cmd_mode = False
        screen.cmd_buffer = ""
        _clear_status(screen, "")
        return True

    if key in ("enter", "\n"):
        _execute_command(screen, screen.cmd_buffer)
        screen.cmd_mode = False
        screen.cmd_buffer = ""
        return True

    if key == "backspace":
        if screen.cmd_buffer:
            screen.cmd_buffer = screen.cmd_buffer[:-1]
            screen.show_status(":" + screen.cmd_buffer)
        return True

    ch = getattr(event, 'character', None)
    if ch is not None:
        screen.cmd_buffer += ch
        screen.show_status(":" + screen.cmd_buffer)
        return True

    if len(key) == 1 or key == "space":
        ch = " " if key == "space" else key
        screen.cmd_buffer += ch
        screen.show_status(":" + screen.cmd_buffer)
        return True

    return True


def _clear_status(screen, msg: str) -> None:
    """Show a status message and exit command mode."""
    screen.cmd_mode = False
    screen.cmd_buffer = ""
    screen.show_status(msg)


def _write_bitmap(app, filepath: str) -> None:
    """Write bitmap data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    data = {"version": "1.0", "bitmaps": app.bitmaps}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _do_save(screen, force: bool, args: list[str]) -> bool:
    """Attempt to save. Returns True on success."""
    app = screen.app
    if args:
        filename = args[0]
        if not filename.endswith(".json"):
            filename += ".json"
        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)
        if os.path.exists(filepath) and filepath != app.file.current_file and not force:
            _clear_status(screen, f"File '{filename}' already exists (add ! to overwrite)")
            return False
        _write_bitmap(app, filepath)
        app.file.set_current_file(filepath)
        app.mark_dirty(False)
        _clear_status(screen, f'"{filename}" written')
        return True

    if not app.file.current_file:
        _clear_status(screen, "No file name")
        return False

    if app.file.check_external_change() and not force:
        _clear_status(screen, "Warning: File modified since reading (add ! to overwrite)")
        return False

    _write_bitmap(app, app.file.current_file)
    app.file.refresh_mtime()
    app.mark_dirty(False)
    fname = os.path.basename(app.file.current_file)
    _clear_status(screen, f'"{fname}" written')
    return True


def _execute_command(screen, cmd_str: str) -> None:
    cmd_str = cmd_str.strip()
    if not cmd_str:
        return

    force = "!" in cmd_str
    cmd_clean = cmd_str.replace("!", "").strip()
    parts = cmd_clean.split()
    command = parts[0]
    args = parts[1:]

    app = screen.app

    if command == "q":
        if force:
            app.exit()
        else:
            app.push_screen(QuitScreen())

    elif command == "w":
        _do_save(screen, force, args)

    elif command == "wq":
        if _do_save(screen, force, args):
            if force:
                app.exit()
            else:
                app.push_screen(QuitScreen())

    elif command == "close":
        if force:
            app.mark_dirty(False)
        if not app.dirty or force:
            app.pop_screen()
            app.push_screen(StartupScreen())
        else:
            app.push_screen(CloseScreen())

    elif command == "scroll":
        if hasattr(screen, 'scroll_mode'):
            if hasattr(screen, 'content_fits') and screen.content_fits:
                _clear_status(screen, "All content visible — scrolling disabled")
            else:
                screen.scroll_mode = True
                screen.update_hints()
                _clear_status(screen, "Scroll mode on")
        else:
            _clear_status(screen, "Unknown command")

    elif command == "noscroll":
        if hasattr(screen, 'scroll_mode'):
            screen.scroll_mode = False
            screen.update_hints()
            _clear_status(screen, "Scroll mode off")
        else:
            _clear_status(screen, "Unknown command")

    elif command == "pan":
        if hasattr(screen, 'pan_flip'):
            screen.pan_flip = True
            screen.update_hints()
            _clear_status(screen, "Pan mode on")
        else:
            _clear_status(screen, "Unknown command")

    elif command == "nopan":
        if hasattr(screen, 'pan_flip'):
            screen.pan_flip = False
            screen.update_hints()
            _clear_status(screen, "Pan mode off")
        else:
            _clear_status(screen, "Unknown command")

    elif command == "help":
        app.push_screen(HelpPopupScreen())

    elif command == "info":
        app.push_screen(InfoScreen(gather_info(app, screen), app, screen))

    elif command == "set":
        if not args:
            _clear_status(screen, "Usage: set step N | set key NAME | set color C")
            return
        sub = args[0]
        sub_args = args[1:]
        if sub == "step":
            if not sub_args:
                _clear_status(screen, "Usage: set step N")
                return
            try:
                n = int(sub_args[0])
                if 1 <= n <= 9:
                    app.step = n
                    if hasattr(screen, 'step'):
                        screen.step = n
                    screen.update_hints()
                    _clear_status(screen, f"Step set to {n}")
                else:
                    _clear_status(screen, "Step must be 1-9")
            except ValueError:
                _clear_status(screen, "Step must be a number (1-9)")
        elif sub == "key":
            if not sub_args:
                _clear_status(screen, "Usage: set key NAME")
                return
            key_name = sub_args[0]
            if " " in key_name:
                _clear_status(screen, "Key name cannot contain spaces")
                return
            is_new = key_name not in app.bitmaps
            if is_new:
                bm = create_default_bitmap()
                bm["location"] = app.find_empty_location()
                app.bitmaps[key_name] = bm
                app.build_key_adjacency()
                app.mark_dirty()
            app.set_current_key(key_name)
            if hasattr(screen, 'switch_to_key'):
                screen.switch_to_key(key_name)
            elif hasattr(screen, 'selected_key'):
                screen.selected_key = key_name
                screen.refresh_map()
            _clear_status(screen, f"Switched to key {key_name}")
        elif sub == "color":
            if not sub_args:
                _clear_status(screen, "Usage: set color C")
                return
            c = sub_args[0].lower()
            if c in "0123456789abcdef":
                app.set_current_color(c)
                _clear_status(screen, f"Color set to {c}")
            else:
                _clear_status(screen, "Color must be 0-9 or A-F")
        elif sub == "colorpixels":
            if sub_args:
                val = sub_args[0].lower()
                if val in ("on", "off", "mixed"):
                    app.color_pixels = val
                else:
                    _clear_status(screen, "Usage: set colorpixels [on|off|mixed]")
                    return
            else:
                cycle = {"on": "off", "off": "mixed", "mixed": "on"}
                app.color_pixels = cycle[app.color_pixels]
            if hasattr(screen, 'refresh_grid'):
                screen.refresh_grid()
            if hasattr(screen, 'refresh_map'):
                screen.refresh_map()
            screen.update_hints()
            _clear_status(screen, f"Color pixels {app.color_pixels}")
        else:
            _clear_status(screen, f"Unknown set subcommand: {sub}")

    elif command == "config":
        if args:
            param = args[0]
            if param == "key":
                key_name = args[1] if len(args) > 1 else ""
                if not key_name:
                    _clear_status(screen, "Usage: config key NAME")
                    return
                if " " in key_name:
                    _clear_status(screen, "Key name cannot contain spaces")
                    return
                is_new = key_name not in app.bitmaps
                if is_new:
                    bm = create_default_bitmap()
                    bm["location"] = app.find_empty_location()
                    app.bitmaps[key_name] = bm
                    app.build_key_adjacency()
                    app.mark_dirty()
                app.set_current_key(key_name)
                if hasattr(screen, 'switch_to_key'):
                    screen.switch_to_key(key_name)
                elif hasattr(screen, 'selected_key'):
                    screen.selected_key = key_name
                    screen.refresh_map()
            else:
                _clear_status(screen, f"Unknown config parameter: {param}")
                return
        else:
            if hasattr(screen, 'selected_key') and screen.selected_key != app.current_key:
                app.set_current_key(screen.selected_key)
        app.push_screen(ConfigScreen())

    else:
        _clear_status(screen, f"Unknown command: {cmd_str}")
