"""Preview HTML and JS code generation from bitmap data."""
import webbrowser

DEFAULT_PIXEL_SIZE = 2

STRATEGIES = ("fast", "balanced", "thorough", "optimal")
FALLBACK_DEFAULT = "balanced"
_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class CodegenService:
    """Generates preview HTML and JS code from bitmap data."""

    PREVIEW_PATH = "/tmp/bitmap-preview.html"

    def __init__(
        self, bitmaps: dict, show_status=None,
        palette: dict[str, dict] | None = None,
        pixel_size: int = DEFAULT_PIXEL_SIZE,
    ):
        self.bitmaps = bitmaps
        self.show_status = show_status or (lambda msg: None)
        self.palette = palette or {}
        self.pixel_size = pixel_size

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
            js_code.extend(self._bitmap_to_js(idx, bm, self.palette, self.pixel_size))
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
    def _bitmap_to_code_lines(
        idx: str, bm: dict, palette: dict[str, dict],
        pixel_size: int = DEFAULT_PIXEL_SIZE,
    ) -> list[str]:
        lines = []
        x_var = bm.get("x", f"x{idx}")
        y_var = bm.get("y", f"y{idx}")
        location = bm.get("location", {"x": 0, "y": 0})
        pixel_size = bm.get("pixelSize", pixel_size)
        pixels = bm.get("bitmap", {}).get("pixels", [])
        if not pixels:
            return lines

        lines.append(f"// Bitmap {idx}")
        lines.append(f"var {x_var} = {location['x'] * pixel_size};")
        lines.append(f"var {y_var} = {location['y'] * pixel_size};")

        for color, rects in CodegenService._extract_rectangles(
            pixels, len(pixels[0]), len(pixels),
            bm.get("codegenStrategy", FALLBACK_DEFAULT),
        ).items():
            lines.append(f"ctx.fillStyle = '{palette.get(color.lower(), {}).get('hex', color)}';")
            for rx, ry, rw, rh in rects:
                lines.append(
                    f"ctx.fillRect({x_var} + {rx * pixel_size}, "
                    f"{y_var} + {ry * pixel_size}, "
                    f"{rw * pixel_size}, {rh * pixel_size});"
                )
        return lines

    def generate_code(self, keys: list[str] | None = None) -> str:
        lines = []
        keys_list = keys if keys is not None else list(self.bitmaps.keys())
        bm_iter = [(k, self.bitmaps[k]) for k in keys_list if k in self.bitmaps]
        for n, (idx, bm) in enumerate(bm_iter):
            lines.extend(self._bitmap_to_code_lines(idx, bm, self.palette, self.pixel_size))
            if n < len(bm_iter) - 1:
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _bitmap_to_js(  # pylint: disable=too-many-locals
        idx: str, bm: dict, palette: dict[str, dict], pixel_size: int = DEFAULT_PIXEL_SIZE
    ) -> list[str]:
        lines = []
        x_var = bm.get("x", f"x{idx}")
        y_var = bm.get("y", f"y{idx}")
        location = bm.get("location", {"x": 0, "y": 0})
        pixel_size = bm.get("pixelSize", pixel_size)
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
    def _compute_single_bitmap_stats(
        bm: dict
    ) -> dict | None:
        pixels = bm.get("bitmap", {}).get("pixels", [])
        if not pixels:
            return None
        width = len(pixels[0])
        height = len(pixels)
        strategy = bm.get("codegenStrategy", FALLBACK_DEFAULT)
        rects_by_color = CodegenService._extract_rectangles(pixels, width, height, strategy)
        rect_count = sum(len(v) for v in rects_by_color.values())
        _color_counts, transparent_count = CodegenService._count_pixel_colors(pixels)
        non_transparent = width * height - transparent_count
        cells_per_rect = round(non_transparent / rect_count, 1) if rect_count else 0
        score = (
            round((non_transparent - rect_count) / non_transparent * 100, 1)
            if non_transparent else 0
        )
        return {
            "rects": rect_count,
            "non_transparent_cells": non_transparent,
            "cells_per_rect": cells_per_rect,
            "score": score,
        }

    @staticmethod
    def generate_code_stats(
        bitmaps: dict, palette: dict[str, dict], keys: list[str] | None = None
    ) -> dict:
        del palette  # kept for caller API compatibility
        per_bitmap = {}
        total_rects = 0
        total_non_transparent = 0
        keys_list = keys if keys is not None else list(bitmaps.keys())
        bm_iter = [(k, bitmaps[k]) for k in keys_list if k in bitmaps]
        for idx, bm in bm_iter:
            stats = CodegenService._compute_single_bitmap_stats(bm)
            if stats is None:
                continue
            per_bitmap[idx] = stats
            total_rects += stats["rects"]
            total_non_transparent += stats["non_transparent_cells"]
        overall_cells_per_rect = round(total_non_transparent / total_rects, 1) if total_rects else 0
        return {
            "per_bitmap": per_bitmap,
            "total_rects": total_rects,
            "total_cells": total_non_transparent,
            "overall_cells_per_rect": overall_cells_per_rect,
            "overall_score": (
                round((total_non_transparent - total_rects) / total_non_transparent * 100, 1)
                if total_non_transparent else 0
            ),
        }

    @staticmethod
    def generate_all_strategy_stats(
        bitmaps: dict, palette: dict[str, dict], keys: list[str] | None = None
    ) -> dict[str, dict]:
        results = {}
        keys_list = keys if keys is not None else list(bitmaps.keys())
        bm_iter = [(k, bitmaps[k]) for k in keys_list if k in bitmaps]
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
            for i, rect in enumerate(rects):
                if used[i]:
                    continue
                for j in range(i + 1, len(rects)):
                    if used[j]:
                        continue
                    m = CodegenService._try_merge(rect, rects[j])
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
    def _detect_sweep_runs(
        pixels: list[str],
        color: str,
        covered: list[list[bool]],
        y: int,
        width: int,
    ) -> list[tuple[int, int]]:
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
        return runs

    @staticmethod
    def _process_sweep_row(
        active: list[tuple[int, int, int, int]],
        rects: list[tuple[int, int, int, int]],
        runs: list[tuple[int, int]],
        y: int,
    ) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
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

        return new_active, rects

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
            runs = CodegenService._detect_sweep_runs(pixels, color, covered, y, width)
            active, rects = CodegenService._process_sweep_row(active, rects, runs, y)

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
    def _flood_fill(
        pixels: list[str],
        covered: list[list[bool]],
        visited: list[list[bool]],
        x: int,
        y: int,
        *,
        color: str,
    ) -> list[tuple[int, int]]:
        width = len(pixels[0])
        height = len(pixels)
        component = [(x, y)]
        stack = [(x, y)]
        visited[y][x] = True
        while stack:
            cx, cy = stack.pop()
            for dx, dy in _DIRECTIONS:
                if (0 <= cx + dx < width and 0 <= cy + dy < height
                    and pixels[cy + dy][cx + dx] == color
                    and not covered[cy + dy][cx + dx]
                    and not visited[cy + dy][cx + dx]):
                    visited[cy + dy][cx + dx] = True
                    stack.append((cx + dx, cy + dy))
                    component.append((cx + dx, cy + dy))
        return component

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
                    comp = CodegenService._flood_fill(
                        pixels, covered, visited, x, y, color=color
                    )
                    components.append(comp)
        return components

    @staticmethod
    def _extract_component_sub_pixels(
        pixels: list[str],
        covered: list[list[bool]],
        color: str,
        component: list[tuple[int, int]],
        bounds: tuple[int, int, int, int],
    ) -> list[str]:
        min_x, min_y, cw, ch = bounds
        comp_set = set(component)
        sub_pixels = []
        for cy in range(min_y, min_y + ch):
            row = []
            for cx in range(min_x, min_x + cw):
                if pixels[cy][cx] == color and not covered[cy][cx] and (cx, cy) in comp_set:
                    row.append(color)
                else:
                    row.append(" ")
            sub_pixels.append("".join(row))
        return sub_pixels

    @staticmethod
    def _pick_best_rects(
        sub_pixels: list[str], cw: int, ch: int
    ) -> dict[str, list[tuple[int, int, int, int]]]:
        hist_rects = CodegenService._extract_rectangles_histogram(sub_pixels, cw, ch)
        sweep_rects = CodegenService._extract_rectangles_sweep(sub_pixels, cw, ch)
        hist_count = sum(len(v) for v in hist_rects.values())
        sweep_count = sum(len(v) for v in sweep_rects.values())
        return hist_rects if hist_count <= sweep_count else sweep_rects

    @staticmethod
    def _translate_rects(
        rects_by_color: dict[str, list[tuple[int, int, int, int]]],
        min_x: int,
        min_y: int,
    ) -> list[tuple[int, int, int, int]]:
        translated = []
        for _col, sub_rects in rects_by_color.items():
            for rx, ry, rw, rh in sub_rects:
                translated.append((rx + min_x, ry + min_y, rw, rh))
        return translated

    @staticmethod
    def _process_color_component(
        pixels: list[str],
        covered: list[list[bool]],
        color: str,
        component: list[tuple[int, int]],
    ) -> list[tuple[int, int, int, int]]:
        if not component:
            return []
        min_x = min(p[0] for p in component)
        max_x = max(p[0] for p in component)
        min_y = min(p[1] for p in component)
        max_y = max(p[1] for p in component)
        cw = max_x - min_x + 1
        ch = max_y - min_y + 1
        sub_pixels = CodegenService._extract_component_sub_pixels(
            pixels, covered, color, component, (min_x, min_y, cw, ch)
        )
        best_rects = CodegenService._pick_best_rects(sub_pixels, cw, ch)
        return CodegenService._translate_rects(best_rects, min_x, min_y)

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
                translated = CodegenService._process_color_component(
                    pixels, covered, color, comp
                )
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
