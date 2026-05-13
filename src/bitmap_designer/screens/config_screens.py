"""Configuration screens for bitmap settings."""
from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input
from textual.containers import Vertical

from ..constants import HINT_ESCAPE

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class ConfigScreen(Screen):
    """Configuration menu screen."""
    _base_title = "Configuration"
    CSS = """
    #menu { margin-top: 1; }
    #hints { opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            yield Static("", id="menu", markup=False)
            yield Static("", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def on_mount(self) -> None:
        self._refresh_values()

    def on_screen_resume(self, _event) -> None:
        self.query_one("#title", Static).update(self.app.title_with_file(self._base_title))
        self._refresh_values()

    def _refresh_values(self):
        idx = str(self.app.current_key)
        bm = self.app.bitmaps.get(idx, {})
        bounds = bm.get("bounds", {"width": 10, "height": 10})
        loc = bm.get("location", {"x": 0, "y": 0})
        keys_list = " ".join(
            f"{k}*" if k == idx else k
            for k in sorted(self.app.bitmaps)
        )

        labels_design = ["[K]ey", "[B]ounds", "[L]ocation"]
        values_design = [
            keys_list if keys_list else str(self.app.current_key),
            f"{bounds['width']} {bounds['height']}",
            f"{loc['x']} {loc['y']}",
        ]
        labels_code = ["[C]ontext", "Pixel [S]ize", "Variable [X]", "Variable [Y]"]
        values_code = [
            bm.get("context", "ctx"),
            str(bm.get("pixelSize", 2)),
            bm.get("x", f"x{idx}"),
            bm.get("y", f"y{idx}"),
        ]

        def _format_group(labels, values):
            pad = max(len(l) for l in labels)
            return "\n".join(
                f"{label}{' ' * (pad - len(label) + 2)}{value}"
                for label, value in zip(labels, values)
            )

        lines = _format_group(labels_design, values_design)
        lines += "\n\n" + _format_group(labels_code, values_code)
        lines += "\n\n[M]anage key\n\n[Escape] back"
        self.query_one("#menu", Static).update(lines)

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "k":
            self.app.push_screen(ConfigKeyScreen())
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
        elif key == "m":
            self.app.push_screen(ConfigKeyManageScreen())
        elif key == "escape":
            self.app.pop_screen()


class ConfigKeyScreen(Screen):
    """Screen to change the current bitmap key."""
    _base_title = "Bitmap Key"
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            self.input = Input(value=self.app.current_key, placeholder="Key", id="key")
            yield self.input
            yield Static("[Enter] set  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def on_screen_resume(self, _event) -> None:
        self.input.value = self.app.current_key

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            val = (self.input.value or "1").strip()
            if val and " " not in val:
                self.app.set_current_key(val)
                if val not in self.app.bitmaps:
                    self.app.bitmaps[val] = self.app.create_default_bitmap()
                    self.app.mark_dirty()
                self.app.pop_screen()
                self.app.show_status(f"Switched to key {val}.")
            else:
                self.app.show_status("Please enter a valid key (no spaces).")

class ConfigKeyManageScreen(Screen):
    """Screen for bitmap key management operations."""
    _base_title = "Manage Key"
    CSS = """
    #menu { margin-top: 1; }
    #info { margin-top: 1; }
    #hints { opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            yield Static("[R]ename key\n[D]elete key\n\n[Escape] back", id="menu", markup=False)
            yield Static("", id="info")
        yield Static("", id="status")

    def on_mount(self) -> None:
        self._refresh_info()

    def on_screen_resume(self, _event) -> None:
        self._refresh_info()

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _refresh_info(self):
        key = self.app.current_key
        bm = self.app.bitmaps.get(key, {})
        bounds = bm.get("bounds", {"width": 10, "height": 10})
        loc = bm.get("location", {"x": 0, "y": 0})
        lines = [
            f"  Key:        {key}",
            f"  Bounds:     {bounds['width']} {bounds['height']}",
            f"  Context:    {bm.get('context', 'ctx')}",
            f"  X:          {bm.get('x', 'x')}",
            f"  Y:          {bm.get('y', 'y')}",
            f"  Location:   {loc['x']} {loc['y']}",
            f"  Pixel Size: {bm.get('pixelSize', 2)}",
        ]
        self.query_one("#info", Static).update("\n".join(lines))

    def on_key(self, event) -> None:
        if event.key.lower() == "r":
            self.app.push_screen(ConfigKeyRenameScreen())
        elif event.key.lower() == "d":
            self.app.push_screen(ConfigKeyDeleteScreen())
        elif event.key == "escape":
            self.app.pop_screen()


class ConfigKeyRenameScreen(Screen):
    """Screen to rename the current bitmap key."""
    _base_title = "Rename Key"
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            self.input = Input(value=self.app.current_key, placeholder="New key", id="key")
            yield self.input
            yield Static("[Enter] rename  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.rename_key()

    def rename_key(self):
        new_key = (self.input.value or "").strip()
        old_key = self.app.current_key
        if not new_key or " " in new_key:
            self.show_status("Please enter a valid key (no spaces).")
            return
        if new_key == old_key:
            self.app.pop_screen()
            return
        if new_key in self.app.bitmaps:
            self.show_status(f"Key '{new_key}' already exists.")
            return
        self.app.bitmaps[new_key] = self.app.bitmaps.pop(old_key)
        if old_key in self.app._undo_stacks:
            self.app._undo_stacks[new_key] = self.app._undo_stacks.pop(old_key)
        if old_key in self.app._redo_stacks:
            self.app._redo_stacks[new_key] = self.app._redo_stacks.pop(old_key)
        self.app.set_current_key(new_key)
        self.app.mark_dirty()
        self.app.show_status(f"Key '{old_key}' renamed to '{new_key}'.")
        self.app.pop_screen()


class ConfigKeyDeleteScreen(Screen):
    """Screen to confirm and delete the current bitmap key."""
    _base_title = "Delete Key"
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            yield Static(
                f"Delete key '{self.app.current_key}' and all its data?",
                id="prompt"
            )
            yield Static("[Y]es  [N]o" + HINT_ESCAPE, id="hints", markup=False)
        yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key.lower() == "y":
            self.delete_key()
        elif event.key.lower() in ("n", "escape"):
            self.app.pop_screen()

    def delete_key(self):
        key = self.app.current_key
        if key not in self.app.bitmaps:
            self.show_status("Key not found.")
            return
        if len(self.app.bitmaps) <= 1:
            self.show_status("Cannot delete the last key.")
            return
        del self.app.bitmaps[key]
        self.app._undo_stacks.pop(key, None)
        self.app._redo_stacks.pop(key, None)
        if self.app.bitmaps:
            self.app.set_current_key(next(iter(self.app.bitmaps)))
        self.app.mark_dirty()
        self.app.pop_screen()  # back to ConfigKeyManageScreen
        self.app.pop_screen()  # back to ConfigScreen
        self.app.show_status(f"Key '{key}' deleted.")


class ConfigBoundsScreen(Screen):
    """Screen to set bitmap width and height."""
    _base_title = "Bitmap Bounds"
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        b = self.app.bitmaps.get(str(self.app.current_key), {}).get("bounds", {})
        bw = b.get("width", 10)
        bh = b.get("height", 10)
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            self.input = Input(value=f"{bw} {bh}", placeholder="width height", id="bounds")
            yield self.input
            yield Static("[Enter] set  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                parts = self.input.value.split()
                if len(parts) >= 2:
                    w = int(parts[0])
                    h = int(parts[1])
                    if w >= 2 and h >= 2:
                        idx = str(self.app.current_key)
                        if idx not in self.app.bitmaps:
                            self.app.bitmaps[idx] = self.app.create_default_bitmap()
                        self.app.bitmaps[idx]["bounds"] = {"width": w, "height": h}
                        self.app.mark_dirty()
                        self.app.pop_screen()
            except ValueError:
                self.app.show_status("Please enter valid width and height (min 2).")


class ConfigContextScreen(Screen):
    """Screen to set the canvas context variable name."""
    _base_title = "Context variable"
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_key), {})
            current = bm.get("context", "ctx")
            self.input = Input(value=current, placeholder="ctx", id="context")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line for messages

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            idx = str(self.app.current_key)
            if idx not in self.app.bitmaps:
                self.app.bitmaps[idx] = self.app.create_default_bitmap()
            self.app.bitmaps[idx]["context"] = self.input.value or "ctx"
            self.app.mark_dirty()
            self.app.pop_screen()
            self.app.show_status("Context saved.")


class ConfigXScreen(Screen):
    """Screen to set the X variable name."""
    _base_title = "X variable"
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_key), {})
            current = bm.get("x", f"x{self.app.current_key}")
            self.input = Input(value=current, placeholder="x", id="x")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            idx = str(self.app.current_key)
            if idx not in self.app.bitmaps:
                self.app.bitmaps[idx] = self.app.create_default_bitmap()
            self.app.bitmaps[idx]["x"] = self.input.value or "x"
            self.app.mark_dirty()
            self.app.pop_screen()
            self.app.show_status("X variable saved.")


class ConfigYScreen(Screen):
    """Screen to set the Y variable name."""
    _base_title = "Y variable"
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_key), {})
            current = bm.get("y", f"y{self.app.current_key}")
            self.input = Input(value=current, placeholder="y", id="y")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            idx = str(self.app.current_key)
            if idx not in self.app.bitmaps:
                self.app.bitmaps[idx] = self.app.create_default_bitmap()
            self.app.bitmaps[idx]["y"] = self.input.value or "y"
            self.app.mark_dirty()
            self.app.pop_screen()
            self.app.show_status("Y variable saved.")


class ConfigLocationScreen(Screen):
    """Screen to set the bitmap origin coordinates."""
    _base_title = "Location (x y)"
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_key), {})
            loc = bm.get("location", {"x": 0, "y": 0})
            self.input = Input(value=f"{loc['x']} {loc['y']}", placeholder="x y", id="location")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                parts = self.input.value.split()
                if len(parts) >= 2:
                    x = int(parts[0])
                    y = int(parts[1])
                    idx = str(self.app.current_key)
                    if idx not in self.app.bitmaps:
                        self.app.bitmaps[idx] = self.app.create_default_bitmap()
                    self.app.bitmaps[idx]["location"] = {"x": x, "y": y}
                    self.app.mark_dirty()
                    self.app.pop_screen()
                    self.app.show_status("Location saved.")
            except ValueError:
                self.app.show_status("Please enter valid x and y coordinates.")


class ConfigPixelScreen(Screen):
    """Screen to set the pixel size for rendering."""
    _base_title = "Pixel Size"
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file(self._base_title), id="title")
        with Vertical():
            bm = self.app.bitmaps.get(str(self.app.current_key), {})
            current = bm.get("pixelSize", 2)
            self.input = Input(value=str(current), placeholder="2", id="pixel")
            yield self.input
            yield Static("[Enter] save  [Escape] cancel", id="hints", markup=False)
        yield Static("", id="status")  # Status line

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            try:
                val = int(self.input.value or "2")
                if val >= 1:
                    idx = str(self.app.current_key)
                    if idx not in self.app.bitmaps:
                        self.app.bitmaps[idx] = self.app.create_default_bitmap()
                    self.app.bitmaps[idx]["pixelSize"] = val
                    self.app.mark_dirty()
                    self.app.pop_screen()
                    self.app.show_status("Pixel size saved.")
            except ValueError:
                self.app.show_status("Please enter a positive integer.")
