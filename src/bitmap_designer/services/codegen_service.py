"""Preview HTML and JS code generation from bitmap data."""
import webbrowser

STRATEGIES = ("fast", "balanced", "thorough", "optimal")
FALLBACK_DEFAULT = "balanced"


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

        strategy = bm.get("codegenStrategy", FALLBACK_DEFAULT)
        rects_by_color = CodegenService._extract_rectangles(
            pixels, len(pixels[0]), len(pixels), strategy
        )
        for color, rects in rects_by_color.items():
            lines.append(f"ctx.fillStyle = '{palette.get(color.lower(), {}).get('hex', color)}';")
            for rx, ry, rw, rh in rects:
                lines.append(
                    f"ctx.fillRect({x_var} + {rx}, {y_var} + {ry}, {rw}, {rh});"
                )
        return lines

    def generate_code(self, keys: list[str] | None = None) -> str:
        lines = []
        bm_iter = [(k, self.bitmaps[k]) for k in (keys if keys is not None else list(self.bitmaps.keys())) if k in self.bitmaps]
        for n, (idx, bm) in enumerate(bm_iter):
            lines.extend(self._bitmap_to_code_lines(idx, bm, self.palette))
            if n < len(bm_iter) - 1:
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

        strategy = bm.get("codegenStrategy", FALLBACK_DEFAULT)
        rectangles = CodegenService._extract_rectangles(pixels, width, height, strategy)
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
    def generate_code_stats(
        bitmaps: dict, palette: dict[str, dict], keys: list[str] | None = None
    ) -> dict:
        per_bitmap = {}
        total_rects = 0
        total_non_transparent = 0
        bm_iter = [(k, bitmaps[k]) for k in (keys if keys is not None else list(bitmaps.keys())) if k in bitmaps]
        for idx, bm in bm_iter:
            pixels = bm.get("bitmap", {}).get("pixels", [])
            if not pixels:
                continue
            width = len(pixels[0])
            height = len(pixels)
            strategy = bm.get("codegenStrategy", FALLBACK_DEFAULT)
            rects_by_color = CodegenService._extract_rectangles(pixels, width, height, strategy)
            rect_count = sum(len(v) for v in rects_by_color.values())
            color_counts, transparent_count = CodegenService._count_pixel_colors(pixels)
            non_transparent = width * height - transparent_count
            cells_per_rect = round(non_transparent / rect_count, 1) if rect_count else 0
            score = round((non_transparent - rect_count) / non_transparent * 100, 1) if non_transparent else 0
            per_bitmap[idx] = {
                "rects": rect_count,
                "non_transparent_cells": non_transparent,
                "cells_per_rect": cells_per_rect,
                "score": score,
            }
            total_rects += rect_count
            total_non_transparent += non_transparent
        overall_cells_per_rect = round(total_non_transparent / total_rects, 1) if total_rects else 0
        return {
            "per_bitmap": per_bitmap,
            "total_rects": total_rects,
            "total_cells": total_non_transparent,
            "overall_cells_per_rect": overall_cells_per_rect,
            "overall_score": round((total_non_transparent - total_rects) / total_non_transparent * 100, 1) if total_non_transparent else 0,
        }

    @staticmethod
    def generate_all_strategy_stats(
        bitmaps: dict, palette: dict[str, dict], keys: list[str] | None = None
    ) -> dict[str, dict]:
        results = {}
        bm_iter = [(k, bitmaps[k]) for k in (keys if keys is not None else list(bitmaps.keys())) if k in bitmaps]
        for strategy in STRATEGIES:
            modified = {}
            for idx, bm in bm_iter:
                modified[idx] = {**bm, "codegenStrategy": strategy}
            results[strategy] = CodegenService.generate_code_stats(modified, palette)
        return results

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
        pixels: list[str], width: int, height: int,
        strategy: str = FALLBACK_DEFAULT,
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        if strategy == "fast":
            rects = CodegenService._extract_rectangles_histogram(pixels, width, height)
        elif strategy == "thorough":
            rects = CodegenService._extract_rectangles_thorough(pixels, width, height)
        elif strategy == "optimal":
            bal = CodegenService._extract_rectangles_sweep(pixels, width, height)
            tho = CodegenService._extract_rectangles_thorough(pixels, width, height)
            bal_count = sum(len(v) for v in bal.values())
            tho_count = sum(len(v) for v in tho.values())
            rects = bal if bal_count <= tho_count else tho
        else:
            rects = CodegenService._extract_rectangles_sweep(pixels, width, height)
        return CodegenService._merge_adjacent_rectangles(rects)

    @staticmethod
    def _extract_rectangles_histogram(
        pixels: list[str], width: int, height: int
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        covered = [[False] * width for _ in range(height)]
        result: dict[str, list[tuple[int, int, int, int]]] = {}

        color_counts, transparent_count = CodegenService._count_pixel_colors(pixels)
        if not color_counts:
            return result

        bg_color = max(color_counts, key=color_counts.get)
        if transparent_count == 0:
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
    def _merge_adjacent_rectangles(
        rects_by_color: dict[str, list[tuple[int, int, int, int]]]
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        result = {}
        for color, rects in rects_by_color.items():
            merged = CodegenService._merge_rect_list(rects)
            if merged:
                result[color] = merged
        return result

    @staticmethod
    def _merge_rect_list(
        rects: list[tuple[int, int, int, int]]
    ) -> list[tuple[int, int, int, int]]:
        if len(rects) <= 1:
            return list(rects)

        rects = list(rects)
        changed = True
        while changed:
            changed = False
            used = [False] * len(rects)
            merged = []
            for i in range(len(rects)):
                if used[i]:
                    continue
                for j in range(i + 1, len(rects)):
                    if used[j]:
                        continue
                    m = CodegenService._try_merge(rects[i], rects[j])
                    if m is not None:
                        rects[i] = m
                        used[j] = True
                        changed = True
                merged.append(rects[i])
            rects = merged
        return rects

    @staticmethod
    def _try_merge(
        a: tuple[int, int, int, int], b: tuple[int, int, int, int]
    ) -> tuple[int, int, int, int] | None:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        if ax == bx and aw == bw and (ay + ah == by or by + bh == ay):
            return (ax, min(ay, by), aw, ah + bh)
        if ay == by and ah == bh and (ax + aw == bx or bx + bw == ax):
            return (min(ax, bx), ay, aw + bw, ah)
        return None

    @staticmethod
    def _sweep_extract_color(
        pixels: list[str],
        color: str,
        covered: list[list[bool]],
        width: int,
        height: int,
    ) -> list[tuple[int, int, int, int]]:
        rects: list[tuple[int, int, int, int]] = []
        active: list[tuple[int, int, int, int]] = []

        for y in range(height):
            runs: list[tuple[int, int]] = []
            x = 0
            while x < width:
                if pixels[y][x] == color and not covered[y][x]:
                    start = x
                    while x < width and pixels[y][x] == color and not covered[y][x]:
                        x += 1
                    runs.append((start, x - start))
                else:
                    x += 1

            new_active: list[tuple[int, int, int, int]] = []
            used = [False] * len(runs)

            for ax, ay, aw, ah in active:
                matched = False
                for ri, (rx, rw) in enumerate(runs):
                    if used[ri]:
                        continue
                    if ax == rx and aw == rw:
                        new_active.append((ax, ay, aw, ah + 1))
                        used[ri] = True
                        matched = True
                        break
                if not matched:
                    rects.append((ax, ay, aw, ah))

            for ri, (rx, rw) in enumerate(runs):
                if not used[ri]:
                    new_active.append((rx, y, rw, 1))

            active = new_active

        rects.extend(active)
        return rects

    @staticmethod
    def _extract_rectangles_sweep(
        pixels: list[str], width: int, height: int
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        covered = [[False] * width for _ in range(height)]
        result: dict[str, list[tuple[int, int, int, int]]] = {}

        color_counts, transparent_count = CodegenService._count_pixel_colors(pixels)
        if not color_counts:
            return result

        bg_color = max(color_counts, key=color_counts.get)
        if transparent_count == 0:
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
            rects = CodegenService._sweep_extract_color(
                pixels, color, covered, width, height
            )
            if rects:
                result[color] = rects
                for rect in rects:
                    CodegenService._mark_rect(covered, *rect)

        return result


    @staticmethod
    def _find_connected_components(
        pixels: list[str],
        color: str,
        covered: list[list[bool]],
        width: int,
        height: int,
    ) -> list[list[tuple[int, int]]]:
        visited = [[False] * width for _ in range(height)]
        components = []
        for y in range(height):
            for x in range(width):
                if pixels[y][x] == color and not covered[y][x] and not visited[y][x]:
                    component = []
                    stack = [(x, y)]
                    visited[y][x] = True
                    while stack:
                        cx, cy = stack.pop()
                        component.append((cx, cy))
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < width and 0 <= ny < height:
                                if (
                                    pixels[ny][nx] == color
                                    and not covered[ny][nx]
                                    and not visited[ny][nx]
                                ):
                                    visited[ny][nx] = True
                                    stack.append((nx, ny))
                    components.append(component)
        return components

    @staticmethod
    def _extract_rectangles_thorough(
        pixels: list[str], width: int, height: int
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        covered = [[False] * width for _ in range(height)]
        result: dict[str, list[tuple[int, int, int, int]]] = {}

        color_counts, transparent_count = CodegenService._count_pixel_colors(pixels)
        if not color_counts:
            return result

        bg_color = max(color_counts, key=color_counts.get)
        if transparent_count == 0:
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
            components = CodegenService._find_connected_components(
                pixels, color, covered, width, height
            )
            for comp in components:
                if not comp:
                    continue
                min_x = min(p[0] for p in comp)
                max_x = max(p[0] for p in comp)
                min_y = min(p[1] for p in comp)
                max_y = max(p[1] for p in comp)
                cw = max_x - min_x + 1
                ch = max_y - min_y + 1

                comp_set = set(comp)
                sub_pixels = []
                for cy in range(min_y, max_y + 1):
                    row = []
                    for cx in range(min_x, min_x + cw):
                        if pixels[cy][cx] == color and not covered[cy][cx] and (cx, cy) in comp_set:
                            row.append(color)
                        else:
                            row.append(" ")
                    sub_pixels.append("".join(row))

                hist_rects = CodegenService._extract_rectangles_histogram(
                    sub_pixels, cw, ch
                )
                sweep_rects = CodegenService._extract_rectangles_sweep(
                    sub_pixels, cw, ch
                )
                hist_count = sum(len(v) for v in hist_rects.values())
                sweep_count = sum(len(v) for v in sweep_rects.values())
                comp_rects = hist_rects if hist_count <= sweep_count else sweep_rects

                translated = []
                for _col, sub_rects in comp_rects.items():
                    for rx, ry, rw, rh in sub_rects:
                        translated.append((rx + min_x, ry + min_y, rw, rh))
                if translated:
                    result.setdefault(color, []).extend(translated)

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
