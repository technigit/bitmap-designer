"""Configuration screens for bitmap settings."""
from __future__ import annotations
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input
from textual.containers import Vertical

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class ConfigScreen(Screen):
    """Configuration menu screen."""
    CSS = """
    #menu { margin-top: 1; }
    #hints { opacity: 0.5; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Configuration"), id="title")
        with Vertical():
            yield Static("", id="menu", markup=False)
        yield Static("", id="status")  # Status line for messages

    def on_mount(self) -> None:
        self._refresh_values()

    def on_screen_resume(self, _event) -> None:
        self._refresh_values()

    def _refresh_values(self):
        idx = str(self.app.current_index)
        bm = self.app.bitmaps.get(idx, {})
        bounds = bm.get("bounds", {"width": 10, "height": 10})
        loc = bm.get("location", {"x": 0, "y": 0})
        labels = [
            "[I]ndex", "[B]ounds", "[C]ontext",
            "Variable [X]", "Variable [Y]",
            "[L]ocation", "Pixel [S]ize",
        ]
        values = [
            idx,
            f"{bounds['width']} {bounds['height']}",
            bm.get("context", "ctx"),
            bm.get("x", f"x{idx}"),
            bm.get("y", f"y{idx}"),
            f"{loc['x']} {loc['y']}",
            str(bm.get("pixelSize", 2)),
        ]
        max_label = max(len(l) for l in labels)
        lines = "\n".join(
            f"{label}{' ' * (max_label - len(label) + 2)}{value}"
            for label, value in zip(labels, values)
        )
        self.query_one("#menu", Static).update(lines)

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


class ConfigIndexScreen(Screen):
    """Screen to change the current bitmap index."""
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Bitmap Index"), id="title")
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
                    self.app.set_current_index(val)
                    if str(val) not in self.app.bitmaps:
                        self.app.bitmaps[str(val)] = self.app.create_default_bitmap()
                    self.app.pop_screen()
                    self.app.show_status(f"Switched to bitmap {val}.")
            except ValueError:
                self.app.show_status("Please enter a positive integer.")


class ConfigBoundsScreen(Screen):
    """Screen to set bitmap width and height."""
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        b = self.app.bitmaps.get(str(self.app.current_index), {}).get("bounds", {})
        bw = b.get("width", 10)
        bh = b.get("height", 10)
        yield Static(self.app.title_with_file("Bitmap Bounds"), id="title")
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
                            self.app.bitmaps[idx] = self.app.create_default_bitmap()
                        self.app.bitmaps[idx]["bounds"] = {"width": w, "height": h}
                        self.app.pop_screen()
            except ValueError:
                self.app.show_status("Please enter valid width and height (min 2).")


class ConfigContextScreen(Screen):
    """Screen to set the canvas context variable name."""
    CSS = """
    Input { margin: 0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Context variable"), id="title")
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
                self.app.bitmaps[idx] = self.app.create_default_bitmap()
            self.app.bitmaps[idx]["context"] = self.input.value or "ctx"
            self.app.pop_screen()
            self.app.show_status("Context saved.")


class ConfigXScreen(Screen):
    """Screen to set the X variable name."""
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("X variable"), id="title")
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
                self.app.bitmaps[idx] = self.app.create_default_bitmap()
            self.app.bitmaps[idx]["x"] = self.input.value or "x"
            self.app.pop_screen()
            self.app.show_status("X variable saved.")


class ConfigYScreen(Screen):
    """Screen to set the Y variable name."""
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Y variable"), id="title")
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
                self.app.bitmaps[idx] = self.app.create_default_bitmap()
            self.app.bitmaps[idx]["y"] = self.input.value or "y"
            self.app.pop_screen()
            self.app.show_status("Y variable saved.")


class ConfigLocationScreen(Screen):
    """Screen to set the bitmap origin coordinates."""
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Location (x y)"), id="title")
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
                        self.app.bitmaps[idx] = self.app.create_default_bitmap()
                    self.app.bitmaps[idx]["location"] = {"x": x, "y": y}
                    self.app.pop_screen()
                    self.app.show_status("Location saved.")
            except ValueError:
                self.app.show_status("Please enter valid x and y coordinates.")


class ConfigPixelScreen(Screen):
    """Screen to set the pixel size for rendering."""
    CSS = """
    Input { margin:0 0; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def __init__(self):
        super().__init__()
        self.input = None

    def compose(self) -> ComposeResult:
        yield Static(self.app.title_with_file("Pixel Size"), id="title")
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
                        self.app.bitmaps[idx] = self.app.create_default_bitmap()
                    self.app.bitmaps[idx]["pixelSize"] = val
                    self.app.pop_screen()
                    self.app.show_status("Pixel size saved.")
            except ValueError:
                self.app.show_status("Please enter a positive integer.")
