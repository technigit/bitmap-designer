from bitmap_designer.services.codegen_service import CodegenService


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
