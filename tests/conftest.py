import pytest


@pytest.fixture
def sample_pixels() -> list[str]:
    return [
        "##  ",
        "##  ",
        "    ",
        "  ##",
    ]


@pytest.fixture
def sample_bitmaps() -> dict:
    return {
        "1": {
            "x": "x",
            "y": "y",
            "location": {"x": 0, "y": 0},
            "pixelSize": 2,
            "bitmap": {
                "pixels": [
                    "##",
                    "##",
                ]
            },
        }
    }


@pytest.fixture
def default_palette() -> dict[str, dict]:
    return {
        "0": {"glyph": " ", "hex": "#000000", "name": "transparent"},
        "1": {"glyph": ".", "hex": "#000000", "name": "black"},
        "2": {"glyph": "\u00b7", "hex": "#FFFFFF", "name": "white"},
        "#": {"glyph": "#", "hex": "#FF4A00", "name": "vermilion"},
    }
