"""Preview HTML and JS code generation from bitmap data."""
import webbrowser

from .constants import COLOR_MAP


class CodegenService:
    """Generates preview HTML and JS code from bitmap data."""

    PREVIEW_PATH = "/tmp/bitmap-preview.html"

    def __init__(self, bitmaps: dict, show_status=None):
        self.bitmaps = bitmaps
        self.show_status = show_status or (lambda msg: None)

    def preview(self) -> None:
        self.save_preview_html()
        try:
            self._open_browser(self.PREVIEW_PATH)
            self.show_status("Preview opened.")
        except (OSError, FileNotFoundError) as e:
            self.show_status(f"Error: {e}")

    def save_preview_html(self) -> None:
        html = self.generate_preview_html()
        with open(self.PREVIEW_PATH, "w", encoding="utf-8") as f:
            f.write(html)

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

    @staticmethod
    def _bitmap_to_js(idx: str, bm: dict) -> list[str]:
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

    @staticmethod
    def _open_browser(path: str) -> None:
        webbrowser.open(f"file://{path}")
