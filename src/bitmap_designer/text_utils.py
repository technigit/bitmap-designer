"""Text formatting utilities for columnar display."""
from __future__ import annotations
import re

_MARKUP_RE = re.compile(r"\[/?\w*(?:#[^]]*)?\]")


def _visible_len(text: str) -> int:
    return len(_MARKUP_RE.sub("", text))


def columnate(rows: list[list[str] | tuple[str, ...]], sep: str = "  ") -> str:
    """Align rows of string cells into columns.

    Args:
        rows: list of lists/tuples of strings.
              Short rows are padded with empty strings.
              A row where all cells are empty-string results in a blank line.
        sep: separator between columns

    Returns:
        A single string ready for Static.update()
    """
    if not rows:
        return ""
    cols = max(len(r) for r in rows)
    widths = []
    for c in range(cols):
        visible_lens = [_visible_len(r[c]) for r in rows if c < len(r)]
        widths.append(max(visible_lens) if visible_lens else 0)
    lines = []
    for row in rows:
        if all(not c for c in row):
            lines.append("")
            continue
        padded = [""] * cols
        for i, cell in enumerate(row):
            padded[i] = cell
        cells = []
        for i, cell in enumerate(padded):
            pad = widths[i] - _visible_len(cell)
            if i < cols - 1 and pad > 0:
                cells.append(cell + " " * pad)
            else:
                cells.append(cell)
        lines.append(sep.join(cells))
    return "\n".join(lines)
