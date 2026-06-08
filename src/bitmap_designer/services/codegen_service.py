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

    @staticmethod
    def _bitmap_to_code_lines(idx: str, bm: dict, palette: dict[str, dict]) -> list[str]:
        lines = []
        x_var = bm.get("x", f"x{idx}")
        y_var = bm.get("y", f"y{idx}")
        location = bm.get("location", {"x": 0, "y": 0})
        pixels = bm.get("bitmap", {}).get("pixels", [])
        if not pixels:
            return lines

        lines.append(f"// Bitmap {idx}")
        lines.append(f"var {x_var} = {location['x']};")
        lines.append(f"var {y_var} = {location['y']};")

        rects_by_color = CodegenService._extract_rectangles(pixels, len(pixels[0]), len(pixels))
        for color, rects in rects_by_color.items():
            lines.append(f"ctx.fillStyle = '{palette.get(color.lower(), {}).get('hex', color)}';")
            for rx, ry, rw, rh in rects:
                lines.append(
                    f"ctx.fillRect({x_var} + {rx}, {y_var} + {ry}, {rw}, {rh});"
                )
        return lines

    def generate_code(self) -> str:
        lines = []
        keys = list(self.bitmaps.keys())
        for n, idx in enumerate(keys):
            lines.extend(self._bitmap_to_code_lines(idx, self.bitmaps[idx], self.palette))
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
        lines.append(f"var {x_var} = {location['x']} * {pixel_size};")
        lines.append(f"var {y_var} = {location['y']} * {pixel_size};")

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
    def _count_pixel_colors(pixels: list[str]
                            ) -> tuple[dict[str, int], int]:
        color_counts: dict[str, int] = {}
        transparent_count = 0
        for row in pixels:
            for char in row:
                if char == " ":
                    transparent_count += 1
                else:
                    color_counts[char] = color_counts.get(char, 0) + 1
        return color_counts, transparent_count

    @staticmethod
    def _mark_bg_pixels(pixels: list[str], covered: list[list[bool]],
                        bg_color: str, width: int, height: int) -> None:
        for y in range(height):
            for x in range(width):
                if pixels[y][x] == bg_color:
                    covered[y][x] = True

    @staticmethod
    def _extract_rectangles(
        pixels: list[str], width: int, height: int
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        covered = [[False] * width for _ in range(height)]
        result: dict[str, list[tuple[int, int, int, int]]] = {}

        color_counts, transparent_count = CodegenService._count_pixel_colors(pixels)

        if not color_counts:
            return result

        bg_color = max(color_counts, key=color_counts.get)

        if transparent_count == 0 and color_counts[bg_color] > width * height // 2:
            result[bg_color] = [(0, 0, width, height)]
            CodegenService._mark_bg_pixels(pixels, covered, bg_color, width, height)
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
                CodegenService._mark_rect(covered, *rect)
            if rects:
                result[color] = rects

        return result

    @staticmethod
    def _mark_rect(covered: list[list[bool]], rx: int, ry: int,
                   rw: int, rh: int) -> None:
        for dy in range(ry, ry + rh):
            for dx in range(rx, rx + rw):
                covered[dy][dx] = True

    @staticmethod
    def _update_histogram(pixels: list[str], covered: list[list[bool]],
                          heights: list[int], *, y: int,
                          color: str, width: int) -> None:
        row = pixels[y]
        for x in range(width):
            if row[x] == color and not covered[y][x]:
                heights[x] += 1
            else:
                heights[x] = 0

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
            CodegenService._update_histogram(pixels, covered, heights,
                                              y=y, color=color, width=width)

            stack: list[int] = []
            for x in range(width + 1):
                cur = heights[x] if x < width else 0
                while stack and cur < heights[stack[-1]]:
                    h = heights[stack.pop()]
                    left = stack[-1] + 1 if stack else 0
                    w = x - left
                    if h * w > best_area:
                        best_rect = (left, y - h + 1, w, h)
                        best_area = h * w
                stack.append(x)

        return best_rect

    @staticmethod
    def _open_browser(path: str) -> None:
        webbrowser.open(f"file://{path}")
