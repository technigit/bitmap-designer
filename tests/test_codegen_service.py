from bitmap_designer.services.codegen_service import CodegenService, STRATEGIES, FALLBACK_DEFAULT


class TestCodegenService:
    def test_generate_code_single_bitmap(self, sample_bitmaps):
        svc = CodegenService(sample_bitmaps, palette={})
        code = svc.generate_code()
        assert "// Bitmap 1" in code
        assert "var x = 0;" in code
        assert "var y = 0;" in code
        assert "ctx.fillStyle" in code
        assert "ctx.fillRect" in code

    def test_generate_code_with_palette(self, sample_bitmaps, default_palette):
        svc = CodegenService(sample_bitmaps, palette=default_palette)
        code = svc.generate_code()
        assert "#" in code
        assert "ctx.fillStyle" in code

    def test_generate_code_empty_bitmaps(self):
        svc = CodegenService({}, palette={})
        assert svc.generate_code() == ""

    def test_generate_code_multiple_bitmaps(self):
        bitmaps = {
            "1": {
                "x": "x1",
                "y": "y1",
                "location": {"x": 0, "y": 0},
                "pixelSize": 1,
                "bitmap": {"pixels": ["##", "##"]},
            },
            "2": {
                "x": "x2",
                "y": "y2",
                "location": {"x": 10, "y": 10},
                "pixelSize": 1,
                "bitmap": {"pixels": ["..", ".."]},
            },
        }
        svc = CodegenService(bitmaps, palette={})
        code = svc.generate_code()
        assert "// Bitmap 1" in code
        assert "// Bitmap 2" in code
        assert code.index("// Bitmap 1") < code.index("// Bitmap 2")

    def test_generate_preview_html(self, sample_bitmaps):
        svc = CodegenService(sample_bitmaps, palette={})
        html = svc.generate_preview_html()
        assert "<!DOCTYPE html>" in html
        assert "<canvas" in html
        assert "ctx.fillRect" in html

    def test_count_pixel_colors(self):
        pixels = ["## ", " . "]
        counts, transparent = CodegenService._count_pixel_colors(pixels)
        assert counts["#"] == 2
        assert counts["."] == 1
        assert transparent == 3

    def test_extract_rectangles_simple(self, sample_pixels):
        pixels = sample_pixels
        height = len(pixels)
        width = len(pixels[0])
        rects = CodegenService._extract_rectangles(pixels, width, height)
        assert "#" in rects
        assert isinstance(rects["#"], list)

    def test_extract_rectangles_empty(self):
        pixels = ["    ", "    "]
        rects = CodegenService._extract_rectangles(pixels, 4, 2)
        assert rects == {}

    def test_extract_rectangles_all_same_color(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles(pixels, 3, 2)
        assert "#" in rects
        assert rects["#"] == [(0, 0, 3, 2)]

    def test_largest_rect_for_color(self):
        pixels = [
            "## ",
            "## ",
            "   ",
        ]
        covered = [[False] * 3 for _ in range(3)]
        rect = CodegenService._largest_rect_for_color(pixels, "#", covered, 3, 3)
        assert rect is not None
        assert rect[2] * rect[3] == 4

    def test_largest_rect_for_color_none(self):
        pixels = ["   ", "   "]
        covered = [[False] * 3 for _ in range(2)]
        rect = CodegenService._largest_rect_for_color(pixels, "#", covered, 3, 2)
        assert rect is None

    def test_mark_rect(self):
        covered = [[False] * 3 for _ in range(3)]
        CodegenService._mark_rect(covered, 1, 1, 2, 2)
        assert covered[1][1] is True
        assert covered[1][2] is True
        assert covered[2][1] is True
        assert covered[2][2] is True
        assert covered[0][0] is False

    def test_generate_code_with_show_status(self, sample_bitmaps):
        messages = []
        svc = CodegenService(sample_bitmaps, show_status=messages.append, palette={})
        svc.generate_code()
        assert len(messages) == 0  # generate_code doesn't call show_status

    def test_bitmap_to_js_without_pixels(self):
        bm = {"bitmap": {"pixels": []}, "location": {"x": 0, "y": 0}}
        result = CodegenService._bitmap_to_js("1", bm, {})
        assert result == []

    def test_bitmap_to_code_lines_without_pixels(self):
        bm = {"bitmap": {"pixels": []}, "location": {"x": 0, "y": 0}}
        result = CodegenService._bitmap_to_code_lines("1", bm, {})
        assert result == []

    def test_extract_rectangles_with_bg_optimization(self):
        pixels = [
            "111",
            "1#1",
            "111",
        ]
        rects = CodegenService._extract_rectangles(pixels, 3, 3)
        assert "1" in rects
        assert "#" in rects

    def test_update_histogram(self):
        pixels = ["# #", "###"]
        covered = [[False] * 3 for _ in range(2)]
        heights = [0, 0, 0]
        CodegenService._update_histogram(
            pixels, covered, heights, y=0, color="#", width=3
        )
        assert heights == [1, 0, 1]

    # --- New tests for rectangle merging ---

    def test_try_merge_vertical(self):
        result = CodegenService._try_merge((0, 0, 5, 2), (0, 2, 5, 3))
        assert result == (0, 0, 5, 5)

    def test_try_merge_vertical_reverse(self):
        result = CodegenService._try_merge((0, 2, 5, 3), (0, 0, 5, 2))
        assert result == (0, 0, 5, 5)

    def test_try_merge_horizontal(self):
        result = CodegenService._try_merge((0, 0, 3, 5), (3, 0, 4, 5))
        assert result == (0, 0, 7, 5)

    def test_try_merge_not_adjacent(self):
        result = CodegenService._try_merge((0, 0, 3, 3), (0, 4, 3, 3))
        assert result is None

    def test_try_merge_different_width(self):
        result = CodegenService._try_merge((0, 0, 3, 2), (0, 2, 4, 2))
        assert result is None

    def test_try_merge_different_height(self):
        result = CodegenService._try_merge((0, 0, 3, 2), (3, 0, 3, 3))
        assert result is None

    def test_merge_rect_list_no_merges(self):
        rects = [(0, 0, 1, 1), (2, 2, 1, 1)]
        merged = CodegenService._merge_rect_list(rects)
        assert len(merged) == 2

    def test_merge_rect_list_multiple_merges_vertical_then_horizontal(self):
        rects = [(0, 0, 5, 2), (0, 2, 5, 3), (5, 0, 3, 5)]
        merged = CodegenService._merge_rect_list(rects)
        assert merged == [(0, 0, 8, 5)]

    def test_merge_adjacent_rectangles_empty(self):
        assert CodegenService._merge_adjacent_rectangles({}) == {}

    def test_merge_adjacent_rectangles_multiple_colors(self):
        rects_by_color = {
            "#": [(0, 0, 3, 2), (0, 2, 3, 2)],
            ".": [(0, 0, 1, 1)],
        }
        merged = CodegenService._merge_adjacent_rectangles(rects_by_color)
        assert merged["#"] == [(0, 0, 3, 4)]
        assert merged["."] == [(0, 0, 1, 1)]

    # --- New tests for sweep extraction ---

    def test_extract_rectangles_sweep_simple(self, sample_pixels):
        pixels = sample_pixels
        height = len(pixels)
        width = len(pixels[0])
        rects = CodegenService._extract_rectangles_sweep(pixels, width, height)
        assert "#" in rects
        assert isinstance(rects["#"], list)

    def test_extract_rectangles_sweep_all_same(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles_sweep(pixels, 3, 2)
        assert "#" in rects
        assert rects["#"] == [(0, 0, 3, 2)]

    def test_extract_rectangles_sweep_empty(self):
        pixels = ["    ", "    "]
        rects = CodegenService._extract_rectangles_sweep(pixels, 4, 2)
        assert rects == {}

    def test_extract_rectangles_sweep_bottleneck(self):
        pixels = [
            "####",
            " ## ",
            " ## ",
            " ## ",
        ]
        width = len(pixels[0])
        height = len(pixels)
        rects = CodegenService._extract_rectangles_sweep(pixels, width, height)
        assert "#" in rects
        assert len(rects["#"]) < 5

    # --- New tests for connected components ---

    def test_find_connected_components_single(self):
        pixels = [
            "## ",
            "## ",
        ]
        covered = [[False] * 3 for _ in range(2)]
        comps = CodegenService._find_connected_components(pixels, "#", covered, 3, 2)
        assert len(comps) == 1
        assert len(comps[0]) == 4

    def test_find_connected_components_disjoint(self):
        pixels = [
            "# #",
            "   ",
        ]
        covered = [[False] * 3 for _ in range(2)]
        comps = CodegenService._find_connected_components(pixels, "#", covered, 3, 2)
        assert len(comps) == 2

    def test_find_connected_components_none(self):
        pixels = ["   ", "   "]
        covered = [[False] * 3 for _ in range(2)]
        comps = CodegenService._find_connected_components(pixels, "#", covered, 3, 2)
        assert comps == []

    # --- New tests for thorough extraction ---

    def test_extract_rectangles_thorough_simple(self, sample_pixels):
        pixels = sample_pixels
        height = len(pixels)
        width = len(pixels[0])
        rects = CodegenService._extract_rectangles_thorough(pixels, width, height)
        assert "#" in rects
        assert isinstance(rects["#"], list)

    def test_extract_rectangles_thorough_empty(self):
        pixels = ["    ", "    "]
        rects = CodegenService._extract_rectangles_thorough(pixels, 4, 2)
        assert rects == {}

    def test_extract_rectangles_thorough_all_same(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles_thorough(pixels, 3, 2)
        assert "#" in rects
        assert rects["#"] == [(0, 0, 3, 2)]

    def test_extract_rectangles_thorough_disjoint(self):
        pixels = [
            "##  ##",
            "##  ##",
        ]
        rects = CodegenService._extract_rectangles_thorough(pixels, 6, 2)
        assert "#" in rects
        assert len(rects["#"]) == 2

    # --- New tests for strategy dispatch ---

    def test_extract_rectangles_fast(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles(pixels, 3, 2, "fast")
        assert "#" in rects

    def test_extract_rectangles_balanced(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles(pixels, 3, 2, "balanced")
        assert "#" in rects

    def test_extract_rectangles_thorough(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles(pixels, 3, 2, "thorough")
        assert "#" in rects

    def test_extract_rectangles_optimal(self):
        pixels = ["###", "###"]
        rects = CodegenService._extract_rectangles(pixels, 3, 2, "optimal")
        assert "#" in rects

    def test_strategies_constant(self):
        assert "fast" in STRATEGIES
        assert "balanced" in STRATEGIES
        assert "thorough" in STRATEGIES
        assert "optimal" in STRATEGIES

    def test_fallback_default(self):
        assert FALLBACK_DEFAULT == "balanced"

    # --- Test strategy metadata passing ---

    def test_bitmap_to_code_lines_respects_strategy(self):
        bm = {
            "x": "x1",
            "y": "y1",
            "location": {"x": 0, "y": 0},
            "pixelSize": 1,
            "codegenStrategy": "fast",
            "bitmap": {"pixels": ["##", "##"]},
        }
        lines = CodegenService._bitmap_to_code_lines("1", bm, {})
        # Should produce output (no error)
        assert len(lines) > 0
        assert "ctx.fillRect" in "\n".join(lines)

    def test_bitmap_to_code_lines_default_strategy(self):
        bm = {
            "x": "x1",
            "y": "y1",
            "location": {"x": 0, "y": 0},
            "pixelSize": 1,
            "bitmap": {"pixels": ["##", "##"]},
        }
        lines = CodegenService._bitmap_to_code_lines("1", bm, {})
        assert len(lines) > 0

    # --- Test post-merge is applied in all strategies ---

    def test_post_merge_applied_to_fast(self):
        pixels = ["##", "##"]
        with_merge = CodegenService._extract_rectangles(pixels, 2, 2, "fast")
        without_merge = CodegenService._extract_rectangles_histogram(pixels, 2, 2)
        # Both should produce same result for simple 2x2
        assert with_merge["#"] == [(0, 0, 2, 2)]
        assert without_merge["#"] == [(0, 0, 2, 2)]

    def test_post_merge_merges_adjacent_rects(self):
        pixels = [
            "###",
            "###",
        ]
        fast = CodegenService._extract_rectangles(pixels, 3, 2, "fast")
        balanced = CodegenService._extract_rectangles(pixels, 3, 2, "balanced")
        thorough = CodegenService._extract_rectangles(pixels, 3, 2, "thorough")
        assert fast["#"] == [(0, 0, 3, 2)]
        assert balanced["#"] == [(0, 0, 3, 2)]
        assert thorough["#"] == [(0, 0, 3, 2)]

    # --- Tests for generate_code_stats ---

    def test_generate_code_stats_single_bitmap(self):
        bitmaps = {
            "1": {
                "x": "x1",
                "y": "y1",
                "location": {"x": 0, "y": 0},
                "pixelSize": 1,
                "bitmap": {"pixels": ["##", "##"]},
            },
        }
        stats = CodegenService.generate_code_stats(bitmaps, palette={})
        assert stats["total_rects"] == 1
        assert stats["total_cells"] == 4
        assert stats["overall_cells_per_rect"] == 4.0
        assert stats["overall_score"] == 75.0
        assert "1" in stats["per_bitmap"]

    def test_generate_code_stats_multiple_bitmaps(self):
        bitmaps = {
            "1": {
                "x": "x1",
                "y": "y1",
                "location": {"x": 0, "y": 0},
                "pixelSize": 1,
                "bitmap": {"pixels": ["##", "##"]},
            },
            "2": {
                "x": "x2",
                "y": "y2",
                "location": {"x": 10, "y": 10},
                "pixelSize": 1,
                "bitmap": {"pixels": ["#.", ".#"]},
            },
        }
        stats = CodegenService.generate_code_stats(bitmaps, palette={})
        assert stats["total_rects"] == 4  # bm1: 1 bg rect, bm2: 3 rects (bg + 2 fg)
        assert stats["total_cells"] == 8
        assert stats["per_bitmap"]["1"]["rects"] == 1
        assert stats["per_bitmap"]["2"]["rects"] == 3

    def test_generate_code_stats_empty_bitmaps(self):
        stats = CodegenService.generate_code_stats({}, palette={})
        assert stats["total_rects"] == 0
        assert stats["total_cells"] == 0
        assert stats["overall_score"] == 0

    def test_generate_code_stats_with_transparency(self):
        bitmaps = {
            "1": {
                "x": "x1",
                "y": "y1",
                "location": {"x": 0, "y": 0},
                "pixelSize": 1,
                "bitmap": {"pixels": ["# ", " #"]},
            },
        }
        stats = CodegenService.generate_code_stats(bitmaps, palette={})
        assert stats["total_cells"] == 2  # 2 non-transparent cells
        assert stats["per_bitmap"]["1"]["non_transparent_cells"] == 2
        # 2 rects (1 bg + 1 fg), 2 cells => (2-2)/2 = 0%
        assert stats["overall_score"] == 0.0

    def test_generate_code_stats_respects_strategy(self):
        bitmaps = {
            "1": {
                "x": "x1",
                "y": "y1",
                "location": {"x": 0, "y": 0},
                "pixelSize": 1,
                "codegenStrategy": "fast",
                "bitmap": {"pixels": ["## ", "## ", "   "]},
            },
        }
        stats = CodegenService.generate_code_stats(bitmaps, palette={})
        assert stats["total_rects"] >= 1
        assert "1" in stats["per_bitmap"]

    # --- Tests for strategy differentiation ---

    def test_fast_vs_thorough_can_differ(self):
        pixels = [
            "####",
            " ## ",
            " ## ",
            " ## ",
        ]
        w, h = len(pixels[0]), len(pixels)
        fast_rects = CodegenService._extract_rectangles(pixels, w, h, "fast")
        thor_rects = CodegenService._extract_rectangles(pixels, w, h, "thorough")
        fast_count = sum(len(v) for v in fast_rects.values())
        thor_count = sum(len(v) for v in thor_rects.values())
        assert fast_count != thor_count
        assert thor_count < fast_count

    def test_thorough_at_least_as_good_as_fast(self):
        shapes = [
            ["####", " ## ", " ## ", " ## "],
            ["#..##", ".##.#", "##..#"],
            ["##..", "#.#.", ".##."],
        ]
        for pixels in shapes:
            w, h = len(pixels[0]), len(pixels)
            fast_rects = CodegenService._extract_rectangles(pixels, w, h, "fast")
            thor_rects = CodegenService._extract_rectangles(pixels, w, h, "thorough")
            fast_count = sum(len(v) for v in fast_rects.values())
            thor_count = sum(len(v) for v in thor_rects.values())
            assert thor_count <= fast_count, f"thorough ({thor_count}) > fast ({fast_count}) for {pixels}"
