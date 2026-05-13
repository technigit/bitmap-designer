"""Constants for the bitmap designer application."""
from pathlib import Path
import os

ASCII_HEADER = "Bitmap Designer"

HINT_ESCAPE = "  [Escape] cancel"

HOME_DIR = str(Path.home())
DEFAULT_BITMAP_DIR = os.path.join(HOME_DIR, "bitmaps")

COLOR_MAP = {
    "1": "#000000", "2": "#FFFFFF", "3": "#FF4A00", "4": "#FFD24A",
    "5": "#5CFF4A", "6": "#4AA8A8", "7": "#C24AFF", "8": "#FF9A00", "9": "#8A4A00",
    "a": "#0f2a66", "b": "#d2d2d2", "c": "#909090", "d": "#ff7a9a",
    "e": "#ffd24a", "f": "#ffffff",
}
