"""Constants for the bitmap designer application."""
from pathlib import Path
import os

from .services.palette_service import HARDCODED_PRESETS

ASCII_HEADER = "Bitmap Designer"

HINT_ESCAPE = "[Escape] cancel"

HOME_DIR = str(Path.home())
DEFAULT_BITMAP_DIR = os.path.join(HOME_DIR, "bitmaps")

def create_default_bitmap() -> dict:
    return {
        "bounds": {"width": 10, "height": 10},
        "context": "ctx",
        "x": "x",
        "y": "y",
        "location": {"x": 0, "y": 0},
        "pixelSize": 2,
        "bitmap": {"pixels": []},
    }

# Backward-compat flat hex map derived from the default preset.
COLOR_MAP: dict[str, str] = {
    cid: cdef["hex"] for cid, cdef in HARDCODED_PRESETS["default"]["colors"].items()
}
