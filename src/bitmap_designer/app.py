import os
import json
import webbrowser
from pathlib import Path
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Footer, Button, Input
from textual.containers import Vertical
from textual.binding import Binding


# ASCII_HEADER = r"""
 #  ___  __   __  _____  __   __   __   __  _____       __   __  _____
 # | __| \ \_/ /  |___ /  | |  | | \ \_/ /        | |  | ||___ /
 # | |    \   /    ___|   | |__| |  \ /          | |__| |  _| |
 # | |__   | |   | |_____|  |  |  |   |          |  |  | ||___|
 # |____|  |_|   |_____||_____|__|   |          |_____|__||_____|
 # """

# ASCII_HEADER = r"""
#  ██████ ██████  ██████  ██████   ██████  ██████ ██████  ██████
#  ██      ██ ████    ██   ██    ████  ██   ████  ██      ██
#  ██████ ██  ████    ██   ██████  ██   ██    ██████   ██
#  ██     ██    ██    ██   ██    ██████    ██    ██
#  ██████ ██████     ██████  ██████  ██████  ██████
#
#  ██████  ██████  ██████  ██████  ██████  ██████  ██████
#  ██       ████   ████  ██    ████ ████   ████   ████
#  ██████   ██    ████  ██████  ██         ████   ██  ████
#     ██   ██    ████  ████    ██████    ████   ██   █
#  ██████  ██████  ██    ██████  ██████   ██████  ██████
# """

ASCII_HEADER = "Bitmap Designer"


HOME_DIR = str(Path.home())
DEFAULT_BITMAP_DIR = os.path.join(HOME_DIR, "bitmaps")


class StartupScreen(Screen):
    CSS = """
    #menu { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Static(ASCII_HEADER, markup=False, id="title")
        with Vertical():
            yield Static("[N]ew Bitmap  [O]pen Bitmap  [Q]uit", id="menu", markup=False)

    def on_mount(self) -> None:
        self.app.title = "Bitmap Designer"

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "q":
            self.app.action_quit()
        elif key == "n":
            self.app.new_bitmap()
        elif key == "o":
            self.app.push_screen(OpenScreen())


class OpenScreen(Screen):
    CSS = """
    #file_list { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.files = []
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        yield Static("Open Bitmap", id="title")
        with Vertical():
            yield Static("", id="file_list")
            yield Static("[Enter] Open  [Escape] Back", id="hints", markup=False)

    def on_mount(self) -> None:
        self.refresh_files()

    def refresh_files(self):
        if not os.path.exists(DEFAULT_BITMAP_DIR):
            self.query_one("#file_list").update("No .json files found.\nCreate ~/bitmaps directory first.")
            return

        self.files = sorted([f for f in os.listdir(DEFAULT_BITMAP_DIR) if f.endswith(".json")])

        if self.files:
            self.selected_idx = 0
            self._update_list()
        else:
            self.query_one("#file_list").update("No .json files found.")

    def _update_list(self):
        lines = []
        for i, f in enumerate(self.files):
            marker = ">" if i == self.selected_idx else " "
            lines.append(f"{marker} {f}")
        self.query_one("#file_list").update("\n".join(lines))

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            if self.files:
                self.open_file()
        elif event.key in ("up", "k") and self.files:
            self.selected_idx = (self.selected_idx - 1) % len(self.files)
            self._update_list()
        elif event.key in ("down", "j") and self.files:
            self.selected_idx = (self.selected_idx + 1) % len(self.files)
            self._update_list()

    def open_file(self):
        filename = self.files[self.selected_idx]
        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)
        self.app.load_file(filepath)


class MainScreen(Screen):
    CSS = """
    #menu { margin-top: 1; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Main Menu", id="title")
        with Vertical():
            yield Static(
                "[D]esign mode\n"
                "[B]itmap index\n"
                "[P]review\n"
                "[S]ave file\n"
                "[G]enerate code\n"
                "[M]anage file\n"
                "[,] Configuration\n"
                "[Escape] back",
                id="menu",
                markup=False
            )
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        key = event.key
        if key == "q":
            self.app.action_quit()
            return
        if key == "comma":
            self.app.push_screen(ConfigScreen())
            return
        key_lower = key.lower()
        if key_lower == "d":
            self.app.push_screen(DesignScreen(self.app.bitmaps.get(str(self.app.current_index), self.app._create_default_bitmap())))
        elif key_lower == "b":
            self.app.push_screen(ConfigIndexScreen())
        elif key_lower == "p":
            self.app.preview()
            self.show_status("Preview opened.")
        elif key_lower == "s":
            self.app.push_screen(SaveScreen())
        elif key_lower == "g":
            self.app.push_screen(CodegenScreen())
        elif key_lower == "m":
            self.app.push_screen(ManageScreen())
        elif key == "escape":
            self.app.push_screen(CloseScreen())


class DesignScreen(Screen):
    CSS = """
    #grid { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self, bitmap_data: dict):
        super().__init__()
        self.bitmap_data = bitmap_data
        self.width = bitmap_data.get("bounds", {}).get("width", 10)
        self.height = bitmap_data.get("bounds", {}).get("height", 10)
        self.pixel_size = bitmap_data.get("pixelSize", 2)
        self.cursor_x = 0
        self.cursor_y = 0
        self.current_color = "1"
        self.pixels = bitmap_data.get("bitmap", {}).get("pixels", [])
        self.undo_stack = []
        self.redo_stack = []

    def compose(self) -> ComposeResult:
        yield Static("Design Mode", id="title")
        with Vertical():
            yield Static("", id="grid")
            yield Static("", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def on_mount(self) -> None:
        self.refresh_grid()
        self._update_hints()

    def refresh_grid(self):
        lines = []
        border = "+" + "-" * (self.width * 2) + "+"  # 2 chars per pixel in UI
        lines.append(border)
        for y in range(self.height):
            row = "|"
            for x in range(self.width):
                if x == self.cursor_x and y == self.cursor_y:
                    # Cursor: show color char with reverse video
                    pixel = self.pixels[y][x] if y < len(self.pixels) and x < len(self.pixels[y]) else " "
                    if pixel == " ":
                        row += "[reverse]  [/]"  # Two spaces, reversed
                    else:
                        row += f"[reverse]{pixel}{pixel}[/]"  # Color char twice, reversed
                else:
                    pixel = self.pixels[y][x] if y < len(self.pixels) and x < len(self.pixels[y]) else " "
                    row += pixel * 2  # Always 2 chars per pixel in UI
            row += "|"
            lines.append(row)
        lines.append(border)

        grid = "\n".join(lines)
        self.query_one("#grid").update(grid)

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "q":
            self.app.action_quit()
            return
        if key == "u":
            self._undo()
            return
        elif key == "ctrl+r":
            self._redo()
            return
        step = 1

        # Check for modifiers in key name (e.g., "shift+left", "ctrl+h")
        if key.startswith("shift"):
            step = 5
        elif key.startswith("ctrl"):
            step = 10
        elif key.startswith("alt"):
            step = 20

        if key in ("left", "h", "a"):
            self.cursor_x = max(0, self.cursor_x - step)
        elif key in ("right", "l", "d"):
            self.cursor_x = min(self.width - 1, self.cursor_x + step)
        elif key in ("up", "k", "w"):
            self.cursor_y = max(0, self.cursor_y - step)
        elif key in ("down", "j", "s"):
            self.cursor_y = min(self.height - 1, self.cursor_y + step)
        elif key == "space":
            self.paint_pixel()
        elif key == "f":
            self.flood_fill()
        elif key == "c":
            self.app.push_screen(ColorScreen())
        elif key == "escape":
            self.app.pop_screen()
        elif key == "p":
            self.app.preview()
            self.show_status("Preview opened.")

        self.refresh_grid()

    def paint_pixel(self):
        self._save_state()
        if len(self.pixels) <= self.cursor_y:
            self.pixels.extend([" " * self.width for _ in range(self.cursor_y - len(self.pixels) + 1)])
        row = list(self.pixels[self.cursor_y])
        if len(row) <= self.cursor_x:
            row.extend([" "] * (self.cursor_x - len(row) + 1))
        row[self.cursor_x] = " " if self.app.current_color == "0" else self.app.current_color
        self.pixels[self.cursor_y] = "".join(row)
        self.app.dirty = True
        self._sync_pixels()
        self.app._save_preview_html()

    def flood_fill(self):
        self._save_state()
        target = self._get_pixel(self.cursor_x, self.cursor_y)
        fill_color = self.app.current_color
        if target == fill_color:
            return
        self._flood_fill(self.cursor_x, self.cursor_y, target, fill_color)
        self.app.dirty = True
        self._sync_pixels()
        self.app._save_preview_html()

    def _get_pixel(self, x: int, y: int) -> str:
        if y < len(self.pixels) and x < len(self.pixels[y]):
            return self.pixels[y][x]
        return " "

    def _set_pixel(self, x: int, y: int, color: str):
        while len(self.pixels) <= y:
            self.pixels.append(" " * self.width)
        row = list(self.pixels[y])
        while len(row) <= x:
            row.append(" ")
        row[x] = " " if color == "0" else color
        self.pixels[y] = "".join(row)

    def _flood_fill(self, x: int, y: int, target: str, fill: str):
        stack = [(x, y)]
        visited = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            if cx < 0 or cx >= self.width or cy < 0 or cy >= self.height:
                continue
            if self._get_pixel(cx, cy) != target:
                continue
            visited.add((cx, cy))
            self._set_pixel(cx, cy, fill)
            stack.append((cx + 1, cy))
            stack.append((cx - 1, cy))
            stack.append((cx, cy + 1))
            stack.append((cx, cy - 1))

    def _sync_pixels(self):
        idx = str(self.app.current_index)
        if idx in self.app.bitmaps:
            self.app.bitmaps[idx]["bitmap"] = {"pixels": self.pixels}

    def _save_state(self):
        self.undo_stack.append([row for row in self.pixels])
        self.redo_stack.clear()
        self._update_hints()

    def _undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append([row for row in self.pixels])
        self.pixels = self.undo_stack.pop()
        self._sync_pixels()
        self.app.dirty = True
        self._update_hints()
        self.refresh_grid()

    def _redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append([row for row in self.pixels])
        self.pixels = self.redo_stack.pop()
        self._sync_pixels()
        self.app.dirty = True
        self._update_hints()
        self.refresh_grid()

    def _update_hints(self):
        from rich.text import Text
        hints = Text()
        hints.append("[arrows/hjkl] move  ")
        hints.append("[space] paint  ")
        hints.append("[C]olor  ")
        hints.append("[F]ill  ")
        hints.append("[R]ect  ")
        hints.append("[P]review  ")
        if not self.undo_stack:
            hints.append("[U]ndo", style="dim")
        else:
            hints.append("[U]ndo")
        hints.append("  ")
        if not self.redo_stack:
            hints.append("[^R]edo", style="dim")
        else:
            hints.append("[^R]edo")
        hints.append("  ")
        hints.append("[Escape] back")
        self.query_one("#hints", Static).update(hints)


class ColorScreen(Screen):
    CSS = """
    #palette { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Select Color", id="title")
        with Vertical():
            yield Static(
                "0: transparent  1: black  2: white  3: red  4: yellow\n"
                "5: green  6: cyan  7: magenta  8: orange  9: brown\n"
                "A-F: extended colors",
                id="palette"
            )
            yield Static("[0-9A-F] select  [Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "q":
            self.app.action_quit()
            return
        if key in "0123456789abcdef":
            self.app.set_current_color(key)
            self.app.pop_screen()
        elif key == "escape":
            self.app.pop_screen()


class SaveScreen(Screen):
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.filename = "Untitled"

    def compose(self) -> ComposeResult:
        yield Static("Save File", id="title")
        with Vertical():
            yield Static(f"Directory: {DEFAULT_BITMAP_DIR}", id="dir")
            self.filename_input = Input(value=self.filename, placeholder="Filename", id="filename")
            yield self.filename_input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.save_file()

    def save_file(self):
        filename = self.filename_input.value or "Untitled"
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)

        if not os.path.exists(DEFAULT_BITMAP_DIR):
            os.makedirs(DEFAULT_BITMAP_DIR, exist_ok=True)

        data = {
            "version": "1.0",
            "bitmaps": self.app.bitmaps,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            self.app.current_file = filepath
            self.app.show_status("File saved.")
            self.app.pop_screen()
        except Exception as e:
            self.app.show_status(f"Error: {e}")


class ManageScreen(Screen):
    CSS = """
    #menu { margin-top: 1; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Manage File", id="title")
        with Vertical():
            yield Static(
                "[R]ename file\n"
                "[D]elete file",
                id="menu",
                markup=False
            )
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key.lower() == "r":
            self.app.push_screen(RenameScreen())
        elif event.key.lower() == "d":
            self.app.push_screen(DeleteScreen())
        elif event.key == "escape":
            self.app.pop_screen()


class RenameScreen(Screen):
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        current = os.path.basename(self.app.current_file or "Untitled.json")
        yield Static("Rename File", id="title")
        with Vertical():
            self.input = Input(value=current.replace(".json", ""), placeholder="New filename", id="filename")
            yield self.input
            yield Static("[Enter] rename  [Escape] cancel", id="hints")

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.rename_file()

    def rename_file(self):
        if not self.app.current_file:
            self.app.show_status("No file to rename.")
            return

        new_name = self.input.value or "Untitled"
        if not new_name.endswith(".json"):
            new_name += ".json"

        dir_path = DEFAULT_BITMAP_DIR
        new_path = os.path.join(dir_path, new_name)

        if os.path.exists(new_path):
            self.app.show_status("File already exists.")
            return

        try:
            os.rename(self.app.current_file, new_path)
            self.app.current_file = new_path
            self.app.show_status("File renamed.")
            self.app.pop_screen()
        except Exception as e:
            self.app.show_status(f"Error: {e}")


class ConfigScreen(Screen):
    CSS = """
    #menu { margin-top: 1; }
    #hints { opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Configuration", id="title")
        with Vertical():
            yield Static(
                "[I]ndex\n"
                "[B]ounds\n"
                "[C]ontext\n"
                "Variable [X]\n"
                "Variable [Y]\n"
                "[L]ocation\n"
                "Pixel [S]ize",
                id="menu",
                markup=False,
            )
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        key = event.key.lower()
        if key == "i":
            self.app.push_screen(ConfigIndexScreen())
        elif key == "b":
            self.app.push_screen(ConfigBoundsScreen())
        elif key == "c":
            self.app.push_screen(ConfigContextScreen())
        elif key == "x":
            self.app.push_screen(ConfigXScreen())
        elif key == "y":
            self.app.push_screen(ConfigYScreen())
        elif key == "l":
            self.app.push_screen(ConfigLocationScreen())
        elif key == "s":
            self.app.push_screen(ConfigPixelScreen())
        elif key == "escape":
            self.app.pop_screen()


class DeleteScreen(Screen):
    """Screen to confirm file deletion."""
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Delete File", id="title")
        with Vertical():
            yield Static("Are you sure you want to delete this file?", id="prompt")
            yield Static("[Y]es  [N]o", id="hints", markup=False)
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key.lower() == "y":
            self.delete_file()
        elif event.key.lower() in ("n", "escape"):
            self.app.pop_screen()

    def delete_file(self):
        if not self.app.current_file or not os.path.exists(self.app.current_file):
            self.app.show_status("No file to delete.")
            return
        try:
            os.remove(self.app.current_file)
            self.app.current_file = None
            self.app.bitmaps = {}
            self.app.dirty = False
            self.app.show_status("File deleted.")
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        except Exception as e:
            self.app.show_status(f"Error: {e}")


class ConfigIndexScreen(Screen):
    """Change the current bitmap index (which bitmap you're editing)."""
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Bitmap Index", id="title")
        with Vertical():
            self.input = Input(value=str(self.app.current_index), placeholder="Index", id="index")
            yield self.input
            yield Static("[Enter] set  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                val = int(self.input.value or "1")
                if val >= 1:
                    self.app.current_index = val
                    if str(val) not in self.app.bitmaps:
                        self.app.bitmaps[str(val)] = self.app._create_default_bitmap()
                    self.app.pop_screen()
                    self.app.show_status(f"Switched to bitmap {val}.")
            except ValueError:
                self.app.show_status("Please enter a positive integer.")


class ConfigBoundsScreen(Screen):
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        b = self.app.bitmaps.get(str(self.app.current_index), {}).get("bounds", {})
        bw = b.get("width", 10)
        bh = b.get("height", 10)
        yield Static("Bitmap Bounds", id="title")
        with Vertical():
            self.input = Input(value=f"{bw} {bh}", placeholder="width height", id="bounds")
            yield self.input
            yield Static("[Enter] set  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                parts = self.input.value.split()
                if len(parts) >= 2:
                    w = int(parts[0])
                    h = int(parts[1])
                    if w >= 2 and h >= 2:
                        idx = str(self.app.current_index)
                        if idx not in self.app.bitmaps:
                            self.app.bitmaps[idx] = self.app._create_default_bitmap()
                        self.app.bitmaps[idx]["bounds"] = {"width": w, "height": h}
                        self.app.pop_screen()
            except ValueError:
                self.app.show_status("Please enter valid width and height (min 2).")


class ConfigContextScreen(Screen):
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Context variable", id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_index), {})
            current = bm.get("context", "ctx")
            self.input = Input(value=current, placeholder="ctx", id="context")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            idx = str(self.app.current_index)
            if idx not in self.app.bitmaps:
                self.app.bitmaps[idx] = self.app._create_default_bitmap()
            self.app.bitmaps[idx]["context"] = self.input.value or "ctx"
            self.app.pop_screen()
            self.app.show_status("Context saved.")


class ConfigXScreen(Screen):
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("X variable", id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_index), {})
            current = bm.get("x", f"x{self.app.current_index}")
            self.input = Input(value=current, placeholder="x", id="x")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            idx = str(self.app.current_index)
            if idx not in self.app.bitmaps:
                self.app.bitmaps[idx] = self.app._create_default_bitmap()
            self.app.bitmaps[idx]["x"] = self.input.value or "x"
            self.app.pop_screen()
            self.app.show_status("X variable saved.")


class ConfigYScreen(Screen):
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Y variable", id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_index), {})
            current = bm.get("y", f"y{self.app.current_index}")
            self.input = Input(value=current, placeholder="y", id="y")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            idx = str(self.app.current_index)
            if idx not in self.app.bitmaps:
                self.app.bitmaps[idx] = self.app._create_default_bitmap()
            self.app.bitmaps[idx]["y"] = self.input.value or "y"
            self.app.pop_screen()
            self.app.show_status("Y variable saved.")


class ConfigLocationScreen(Screen):
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Location (x y)", id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_index), {})
            loc = bm.get("location", {"x": 0, "y": 0})
            self.input = Input(value=f"{loc['x']} {loc['y']}", placeholder="x y", id="location")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                parts = self.input.value.split()
                if len(parts) >= 2:
                    x = int(parts[0])
                    y = int(parts[1])
                    idx = str(self.app.current_index)
                    if idx not in self.app.bitmaps:
                        self.app.bitmaps[idx] = self.app._create_default_bitmap()
                    self.app.bitmaps[idx]["location"] = {"x": x, "y": y}
                    self.app.pop_screen()
                    self.app.show_status("Location saved.")
            except ValueError:
                self.app.show_status("Please enter valid x and y coordinates.")


class ConfigPixelScreen(Screen):
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Pixel Size", id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_index), {})
            current = bm.get("pixelSize", 2)
            self.input = Input(value=str(current), placeholder="2", id="pixel")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                val = int(self.input.value or "2")
                if val >= 1:
                    idx = str(self.app.current_index)
                    if idx not in self.app.bitmaps:
                        self.app.bitmaps[idx] = self.app._create_default_bitmap()
                    self.app.bitmaps[idx]["pixelSize"] = val
                    self.app.pop_screen()
                    self.app.show_status("Pixel size saved.")
            except ValueError:
                self.app.show_status("Please enter a positive integer.")


class QuitScreen(Screen):
    """Screen shown when user tries to quit (q from anywhere)."""

    def on_mount(self) -> None:
        if not self.app.dirty:
            self.app.exit()

    def compose(self) -> ComposeResult:
        yield Static("Quit", id="title")
        with Vertical():
            yield Static("Really quit? (y/N)", id="prompt")

    def on_key(self, event) -> None:
        if event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(QuitSaveFileFirstScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()


class QuitSaveFileFirstScreen(Screen):
    """Screen shown during quit flow when asking to save before quitting."""
    def compose(self) -> ComposeResult:
        yield Static("Quit - Save", id="title")
        with Vertical():
            yield Static("Save file first? (Y/n)", id="prompt")

    def on_key(self, event) -> None:
        if event.key in ("enter", "\n") or event.key.lower() == "y":
            self.app.push_screen(QuitSaveScreen())
        elif event.key.lower() == "n":
            self.app.exit()
        elif event.key == "escape":
            self.app.pop_screen()


class QuitSaveScreen(Screen):
    """Save screen for quit flow."""
    CSS = """
    Input { margin: 1 0; }
    #hints { opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.filename = "Untitled"

    def compose(self) -> ComposeResult:
        yield Static("Save File", id="title")
        with Vertical():
            yield Static(f"Directory: {DEFAULT_BITMAP_DIR}", id="dir")
            self.filename_input = Input(value=self.filename, placeholder="Filename", id="filename")
            yield self.filename_input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.save_file()

    def save_file(self):
        filename = self.filename_input.value or "Untitled"
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)

        if not os.path.exists(DEFAULT_BITMAP_DIR):
            os.makedirs(DEFAULT_BITMAP_DIR, exist_ok=True)

        data = {
            "version": "1.0",
            "bitmaps": self.app.bitmaps,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            self.app.current_file = filepath
            self.app.dirty = False
            self.app.exit()
        except Exception as e:
            self.app.show_status(f"Error: {e}")


class CloseScreen(Screen):
    """Screen shown when user tries to close (Escape from MainScreen)."""

    def on_mount(self) -> None:
        if not self.app.dirty:
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())

    def compose(self) -> ComposeResult:
        yield Static("Close", id="title")
        with Vertical():
            yield Static("Really close? (y/N)", id="prompt")

    def on_key(self, event) -> None:
        if event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(SaveFileFirstScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()


class SaveFileFirstScreen(Screen):
    """Screen shown during close flow when asking to save before closing."""
    def compose(self) -> ComposeResult:
        yield Static("Close - Save", id="title")
        with Vertical():
            yield Static("Save file first? (Y/n)", id="prompt")

    def on_key(self, event) -> None:
        if event.key in ("enter", "\n") or event.key.lower() == "y":
            self.app.push_screen(SaveScreenForClose())
        elif event.key.lower() == "n":
            self.app.pop_screen()
            self.app.push_screen(AreYouSureScreen())
        elif event.key == "escape":
            self.app.pop_screen()
            self.app.push_screen(MainScreen())


class SaveScreenForClose(Screen):
    CSS = """
    Input { margin: 1 0; }
    #hints { opacity: 0.5; }
    """

    def __init__(self):
        super().__init__()
        self.filename = "Untitled"

    def compose(self) -> ComposeResult:
        yield Static("Save File", id="title")
        with Vertical():
            yield Static(f"Directory: {DEFAULT_BITMAP_DIR}", id="dir")
            self.filename_input = Input(value=self.filename, placeholder="Filename", id="filename")
            yield self.filename_input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key.lower() == "q":
            self.app.action_quit()
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.save_file()

    def save_file(self):
        filename = self.filename_input.value or "Untitled"
        if not filename.endswith(".json"):
            filename += ".json"

        filepath = os.path.join(DEFAULT_BITMAP_DIR, filename)

        if not os.path.exists(DEFAULT_BITMAP_DIR):
            os.makedirs(DEFAULT_BITMAP_DIR, exist_ok=True)

        data = {
            "version": "1.0",
            "bitmaps": self.app.bitmaps,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            self.app.current_file = filepath
            self.app.dirty = False
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        except Exception as e:
            self.app.show_status(f"Error: {e}")


class AreYouSureScreen(Screen):
    """Screen shown during close flow when user says 'no' to saving."""
    def compose(self) -> ComposeResult:
        yield Static("Close - Confirm", id="title")
        with Vertical():
            yield Static("Are you sure? (y/N)", id="prompt")

    def on_key(self, event) -> None:
        if event.key.lower() == "y":
            self.app.pop_screen()
            self.app.push_screen(StartupScreen())
        elif event.key in ("enter", "\n") or event.key.lower() in ("n", "escape"):
            self.app.pop_screen()
            self.app.push_screen(MainScreen())


class CodegenScreen(Screen):
    CSS = """
    #code { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Code Generation", id="title")
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


class BitmapDesignerApp(App):
    CSS = """
    #title { text-align: center; text-style: bold; margin-top: 1; margin-bottom: 2; }
    #hints { margin-top: 1; opacity: 0.5; }
    Vertical { margin-left: 3; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.current_file = None
        self.bitmaps = {}
        self.current_index = 1
        self.current_color = "1"
        self.dirty = False

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(StartupScreen())

    def action_quit(self) -> None:
        self.push_screen(QuitScreen())

    def show_status(self, message: str) -> None:
        """Show a status message on the current screen's #status widget."""
        try:
            screen = self.screen
            if hasattr(screen, 'show_status'):
                screen.show_status(message)
        except Exception:
            pass

    def new_bitmap(self):
        self.bitmaps = {}
        self.current_index = 1
        self.bitmaps["1"] = self._create_default_bitmap()
        self.dirty = False
        self.push_screen(MainScreen())

    def load_file(self, filepath: str):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                self.current_file = filepath
                if self.bitmaps:
                    self.current_index = int(next(iter(self.bitmaps.keys())))
                self.dirty = False
                self.push_screen(MainScreen())
        except Exception as e:
            self.show_status(f"Error loading file: {e}")

    def set_current_color(self, color: str):
        self.current_color = color

    def preview(self):
        self._save_preview_html()
        try:
            self._open_browser("/tmp/bitmap-preview.html")
            self.show_status("Preview opened.")
        except Exception as e:
            self.show_status(f"Error: {e}")

    def _save_preview_html(self):
        html = self.generate_preview_html()
        preview_path = "/tmp/bitmap-preview.html"
        with open(preview_path, "w") as f:
            f.write(html)

    def _open_browser(self, path: str):
        import platform
        import webbrowser
        webbrowser.open(f"file://{path}")

    def generate_preview_html(self) -> str:
        color_map = {
            "1": "#000000", "2": "#FFFFFF", "3": "#FF4A00", "4": "#FFD24A",
            "5": "#5CFF4A", "6": "#4AA8A8", "7": "#C24AFF", "8": "#FF9A00", "9": "#8A4A00",
            "a": "#0f2a66", "b": "#d2d2d2", "c": "#909090", "d": "#ff7a9a",
            "e": "#ffd24a", "f": "#ffffff",
        }

        js_code = []
        for idx, bm in self.bitmaps.items():
            x_var = bm.get("x", f"x{idx}")
            y_var = bm.get("y", f"y{idx}")
            location = bm.get("location", {"x": 0, "y": 0})
            pixel_size = bm.get("pixelSize", 2)
            pixels = bm.get("bitmap", {}).get("pixels", [])

            js_code.append(f"// Bitmap {idx}")
            js_code.append(f"const {x_var} = {location['x']};")
            js_code.append(f"const {y_var} = {location['y']};")

            for y, row in enumerate(pixels):
                for x, char in enumerate(row):
                    if char != " ":
                        color = color_map.get(char.lower(), char)
                        js_code.append(f"ctx.fillStyle = '{color}';")
                        js_code.append(f"ctx.fillRect({x_var} + {x} * {pixel_size}, {y_var} + {y} * {pixel_size}, {pixel_size}, {pixel_size});")

        canvas_js = "\n    ".join(js_code)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="2">
    <title>Bitmap Preview</title>
    <style>
        body {{ margin: 20px; background: #222; }}
        canvas {{ border: 1px solid #666; }}
    </style>
</head>
<body>
    <canvas id="canvas" width="800" height="600"></canvas>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        {canvas_js}
    </script>
</body>
</html>"""

    def generate_code(self) -> str:
        lines = []
        for idx, bm in self.bitmaps.items():
            x_var = bm.get("x", f"x{idx}")
            y_var = bm.get("y", f"y{idx}")
            location = bm.get("location", {"x": 0, "y": 0})
            pixels = bm.get("bitmap", {}).get("pixels", [])

            lines.append(f"// Bitmap {idx}")
            lines.append(f"const {x_var} = {location['x']};")
            lines.append(f"const {y_var} = {location['y']};")

            for y, row in enumerate(pixels):
                for x, char in enumerate(row):
                    if char != " ":
                        lines.append(f"ctx.fillStyle('{char}');")
                        lines.append(f"ctx.fillRect({x_var} + {x}, {y_var} + {y}, 1, 1);")

        return "\n".join(lines)

    def _create_default_bitmap(self) -> dict:
        return {
            "bounds": {"width": 10, "height": 10},
            "context": "ctx",
            "x": "x1",
            "y": "y1",
            "location": {"x": 0, "y": 0},
            "pixelSize": 2,
            "bitmap": {"pixels": []},
        }


def run():
    app = BitmapDesignerApp()
    app.run()


if __name__ == "__main__":
    run()