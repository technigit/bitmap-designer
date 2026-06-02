"""Preview HTML and JS code generation from bitmap data."""
import webbrowser


class CodegenService:
    """Generates preview HTML and JS code from bitmap data."""

    PREVIEW_PATH = "/tmp/bitmap-preview.html"

    def __init__(self, bitmaps: dict, show_status=None, palette: dict[str, dict] | None = None):
        self.bitmaps = bitmaps
        self.show_status = show_status or (lambda msg: None)
        self.palette = palette or {}

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
            js_code.extend(self._bitmap_to_js(idx, bm, self.palette))
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
        keys = list(self.bitmaps.keys())
        for n, idx in enumerate(keys):
            bm = self.bitmaps[idx]
            x_var = bm.get("x", f"x{idx}")
            y_var = bm.get("y", f"y{idx}")
            location = bm.get("location", {"x": 0, "y": 0})
            pixels = bm.get("bitmap", {}).get("pixels", [])
            if not pixels:
                continue
            height = len(pixels)
            width = len(pixels[0])

            lines.append(f"// Bitmap {idx}")
            lines.append(f"var {x_var} = {location['x']};")
            lines.append(f"var {y_var} = {location['y']};")

            rectangles = self._extract_rectangles(pixels, width, height)
            for color, rects in rectangles.items():
                entry = self.palette.get(color.lower(), {})
                color_value = entry.get("hex", color)
                lines.append(f"ctx.fillStyle = '{color_value}';")
                for rx, ry, rw, rh in rects:
                    lines.append(
                        f"ctx.fillRect({x_var} + {rx}, {y_var} + {ry}, {rw}, {rh});"
                    )
            if n < len(keys) - 1:
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _bitmap_to_js(  # pylint: disable=too-many-locals
        idx: str, bm: dict, palette: dict[str, dict]
    ) -> list[str]:
        lines = []
        x_var = bm.get("x", f"x{idx}")
        y_var = bm.get("y", f"y{idx}")
        location = bm.get("location", {"x": 0, "y": 0})
        pixel_size = bm.get("pixelSize", 2)
        pixels = bm.get("bitmap", {}).get("pixels", [])
        if not pixels:
            return lines
        height = len(pixels)
        width = len(pixels[0])

        lines.append(f"// Bitmap {idx}")
        lines.append(f"var {x_var} = {location['x']};")
        lines.append(f"var {y_var} = {location['y']};")

        rectangles = CodegenService._extract_rectangles(pixels, width, height)
        for color, rects in rectangles.items():
            entry = palette.get(color.lower(), {})
            color_value = entry.get("hex", color)
            lines.append(f"ctx.fillStyle = '{color_value}';")
            for rx, ry, rw, rh in rects:
                lines.append(
                    f"ctx.fillRect({x_var} + {rx} * {pixel_size}, "
                    f"{y_var} + {ry} * {pixel_size}, "
                    f"{rw} * {pixel_size}, {rh} * {pixel_size});"
                )
        return lines

    @staticmethod
    def _extract_rectangles(
        pixels: list[str], width: int, height: int
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        covered = [[False] * width for _ in range(height)]
        result: dict[str, list[tuple[int, int, int, int]]] = {}

        color_counts = {}
        transparent_count = 0
        for row in pixels:
            for char in row:
                if char == " ":
                    transparent_count += 1
                else:
                    color_counts[char] = color_counts.get(char, 0) + 1

        if not color_counts:
            return result

        bg_color = max(color_counts, key=color_counts.get)
        total = width * height
        use_bg_fill = transparent_count == 0 and color_counts[bg_color] > total // 2

        if use_bg_fill:
            result[bg_color] = [(0, 0, width, height)]
            for y in range(height):
                for x in range(width):
                    if pixels[y][x] == bg_color:
                        covered[y][x] = True
            colors = sorted(
                (c for c in color_counts if c != bg_color),
                key=lambda c: color_counts[c],
                reverse=True,
            )
        else:
            colors = sorted(
                color_counts.keys(), key=lambda c: color_counts[c], reverse=True
            )

        for color in colors:
            rects = []
            while True:
                rect = CodegenService._largest_rect_for_color(
                    pixels, color, covered, width, height
                )
                if rect is None:
                    break
                rects.append(rect)
                rx, ry, rw, rh = rect
                for dy in range(ry, ry + rh):
                    for dx in range(rx, rx + rw):
                        covered[dy][dx] = True
            if rects:
                result[color] = rects

        return result

    @staticmethod
    def _largest_rect_for_color(
        pixels: list[str],
        color: str,
        covered: list[list[bool]],
        width: int,
        height: int,
    ) -> tuple[int, int, int, int] | None:
        heights = [0] * width
        best_rect = None
        best_area = 0

        for y in range(height):
            row = pixels[y]
            for x in range(width):
                if row[x] == color and not covered[y][x]:
                    heights[x] += 1
                else:
                    heights[x] = 0

            stack: list[int] = []
            for x in range(width + 1):
                curr_h = heights[x] if x < width else 0
                while stack and curr_h < heights[stack[-1]]:
                    h = heights[stack.pop()]
                    left = stack[-1] + 1 if stack else 0
                    w = x - left
                    area = h * w
                    if area > best_area:
                        top = y - h + 1
                        best_rect = (left, top, w, h)
                        best_area = area
                stack.append(x)

        return best_rect

    @staticmethod
    def _open_browser(path: str) -> None:
        webbrowser.open(f"file://{path}")
