"""Main application class and entry point."""
import json
import os
import webbrowser
from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.binding import Binding

from .constants import COLOR_MAP, DEFAULT_BITMAP_DIR
from .screens import StartupScreen, MainScreen, QuitScreen


class BitmapDesignerApp(App):
    """Textual App subclass orchestrating all screens and application state."""
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
        self.current_file_mtime = None
        self.bitmaps = {}
        self.current_key = "1"
        self.current_color = "1"
        self.dirty = False

    def mark_dirty(self, value: bool = True) -> None:
        self.dirty = value

    def set_current_file(self, path: str | None) -> None:
        self.current_file = path
        self.refresh_mtime()

    def title_with_file(self, base_title: str) -> str:
        if self.current_file:
            return f"{base_title} - {os.path.basename(self.current_file)}"
        return base_title

    def set_bitmaps(self, bitmaps: dict) -> None:
        self.bitmaps = bitmaps

    def set_current_key(self, key: str) -> None:
        self.current_key = key

    def refresh_mtime(self) -> None:
        try:
            self.current_file_mtime = os.path.getmtime(self.current_file) if self.current_file and os.path.exists(self.current_file) else None
        except OSError:
            self.current_file_mtime = None

    def check_external_change(self) -> bool:
        if not self.current_file or not os.path.exists(self.current_file):
            return False
        try:
            return os.path.getmtime(self.current_file) != self.current_file_mtime
        except OSError:
            return False

    def reload_file(self) -> None:
        if not self.current_file or not os.path.exists(self.current_file):
            return
        try:
            with open(self.current_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                if self.bitmaps:
                    self.current_key = next(iter(self.bitmaps.keys()))
                self.dirty = False
                self.refresh_mtime()
        except (OSError, json.JSONDecodeError) as e:
            self.show_status(f"Error reloading file: {e}")

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(StartupScreen())

    async def action_quit(self) -> None:
        self.push_screen(QuitScreen())

    # Show a status message on the current screen's #status widget.

    def show_status(self, message: str) -> None:
        try:
            screen = self.screen
            if hasattr(screen, 'show_status'):
                screen.show_status(message)
        except Exception:  # pylint: disable=W0718
            pass

    # Create a new blank bitmap and open the main menu.

    def new_bitmap(self):
        self.bitmaps = {}
        self.current_key = "1"
        self.bitmaps["1"] = self.create_default_bitmap()
        self.set_current_file(os.path.join(DEFAULT_BITMAP_DIR, "Untitled.json"))
        self.dirty = False
        self.set_current_color("1")
        self.push_screen(MainScreen())

    # Load bitmaps from a JSON file and open the main menu.

    def load_file(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bitmaps = data.get("bitmaps", {})
                self.set_current_file(filepath)
                if self.bitmaps:
                    self.current_key = next(iter(self.bitmaps.keys()))
                self.dirty = False
                self.push_screen(MainScreen())
        except (OSError, json.JSONDecodeError) as e:
            self.show_status(f"Error loading file: {e}")

    def set_current_color(self, color: str):
        self.current_color = color

    # Generate the preview HTML and open it in a browser.

    def preview(self):
        self.save_preview_html()
        try:
            self._open_browser("/tmp/bitmap-preview.html")
            self.show_status("Preview opened.")
        except (OSError, FileNotFoundError) as e:
            self.show_status(f"Error: {e}")

    # Write the preview HTML to /tmp.

    def save_preview_html(self):
        html = self.generate_preview_html()
        preview_path = "/tmp/bitmap-preview.html"
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html)

    # Open a local file in the system browser.

    def _open_browser(self, path: str):
        webbrowser.open(f"file://{path}")

    # Generate JavaScript fillRect calls for a single bitmap's pixels.

    def _bitmap_to_js(self, idx: str, bm: dict) -> list[str]:
        lines = []
        x_var = bm.get("x", f"x{idx}")
        y_var = bm.get("y", f"y{idx}")
        location = bm.get("location", {"x": 0, "y": 0})
        pixel_size = bm.get("pixelSize", 2)
        pixels = bm.get("bitmap", {}).get("pixels", [])

        lines.append(f"// Bitmap {idx}")
        lines.append(f"var {x_var} = {location['x']};")
        lines.append(f"var {y_var} = {location['y']};")

        for y, row in enumerate(pixels):
            for x, char in enumerate(row):
                if char != " ":
                    color = COLOR_MAP.get(char.lower(), char)
                    lines.append(f"ctx.fillStyle = '{color}';")
                    rect = f"{x_var} + {x} * {pixel_size},"
                    rect += f"{y_var} + {y} * {pixel_size}, {pixel_size}, {pixel_size}"
                    lines.append(f"ctx.fillRect({rect});")
        return lines

    # Build the complete HTML preview page with canvas rendering.

    def generate_preview_html(self) -> str:
        js_code = []
        for idx, bm in self.bitmaps.items():
            js_code.extend(self._bitmap_to_js(idx, bm))

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

    # Build the JavaScript code string for all bitmaps.

    def generate_code(self) -> str:
        lines = []
        for idx, bm in self.bitmaps.items():
            x_var = bm.get("x", f"x{idx}")
            y_var = bm.get("y", f"y{idx}")
            location = bm.get("location", {"x": 0, "y": 0})
            pixels = bm.get("bitmap", {}).get("pixels", [])

            lines.append(f"// Bitmap {idx}")
            lines.append(f"var {x_var} = {location['x']};")
            lines.append(f"var {y_var} = {location['y']};")

            for y, row in enumerate(pixels):
                for x, char in enumerate(row):
                    if char != " ":
                        lines.append(f"ctx.fillStyle('{char}');")
                        lines.append(f"ctx.fillRect({x_var} + {x}, {y_var} + {y}, 1, 1);")

        return "\n".join(lines)

    # Return a default bitmap configuration dict.

    def create_default_bitmap(self, key: str = "1") -> dict:
        return {
            "bounds": {"width": 10, "height": 10},
            "context": "ctx",
            "x": "x",
            "y": "y",
            "location": {"x": 0, "y": 0},
            "pixelSize": 2,
            "bitmap": {"pixels": []},
        }


def run():
    """Run the bitmap designer application."""
    app = BitmapDesignerApp()
    app.run()


if __name__ == "__main__":
    run()
