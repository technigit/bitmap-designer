"""Help screen showing all keybindings."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
from rich.text import Text

from .popup_screen import PopupScreen


def _build_pages(data: list[tuple[str, list[tuple[str, str]]]]) -> list[str]:
    """Pad and align help page data into formatted Rich markup strings."""
    max_w = max(
        len(Text.from_markup(k).plain) for _, items in data for k, _ in items
    )
    target = 2 + max_w + 4
    pages = []
    for title, items in data:
        lines = [title]
        for key, desc in items:
            w = len(Text.from_markup(key).plain)
            pad = target - 2 - w
            lines.append(f"  {key}{' ' * pad}{desc}")
        pages.append("\n".join(lines))
    max_lines = max(p.count("\n") + 1 for p in pages)
    return [p + "\n" * (max_lines - p.count("\n") - 1) for p in pages]


_DESIGN_HELP_DATA = [
    ("[b]Movement[/]", [
        ("[bold]hjkl[/] / arrows", "Move cursor (or scroll in scroll mode)"),
        ("[bold]^[/] / [bold]$[/]", "First / last non-blank in current row"),
        ("[bold]0[/]", "Column 0"),
        ("[bold]Enter[/]", "Beginning of next line"),
        ("[bold]gg[/] / [bold]1G[/]", "Top row, first non-blank"),
        ("[bold]G[/]", "Bottom row, first non-blank"),
        ("[bold]nG[/]", "Row n, first non-blank"),
        ("[bold]H[/] / [bold]M[/] / [bold]L[/]", "Viewport top / middle / bottom row"),
        ("[bold]g^[/] / [bold]g$[/]", "Viewport left / right non-blank"),
        ("1-9", "Prefix count (e.g. 5j → 5 down)"),
    ]),
    ("[b]Editing[/]", [
        ("[bold]space[/]", "Paint pixel at cursor (advances right)"),
        ("[bold]x[/]", "Delete pixel at cursor"),
        ("[bold]D[/] / [bold]dd[/]", "Delete row / N rows"),
        ("[bold]e[/]", "Eyedropper — pick color under cursor"),
        ("[bold]f[/]", "Flood fill"),
        ("[bold]r[/]", "Rectangle mode"),
        ("[bold]c[/]", "Color picker"),
        ("[bold]u[/] / [bold]\u2303R[/]", "Undo / Redo"),
        ("[bold]m[/]", "Map / remap"),
    ]),
    ("[b]Visual / Yank / Put[/]", [
        ("[bold]v[/]", "Start visual selection"),
        ("[bold]y[/]", "Yank selection"),
        ("[bold]yy[/]", "Yank current row"),
        ("[bold]p[/]", "Paste clipboard at cursor"),
        ("[bold]P[/]", "Preview HTML"),
        ("[bold].[/]", "Repeat last action"),
    ]),
    ("[b]Scroll & Viewport[/]", [
        ("[bold]\\[/]", "Toggle scroll mode"),
        ("[bold]zl[/] / [bold]zh[/]", "Scroll right / left 1 column"),
        ("[bold]zL[/] / [bold]zH[/]", "Scroll right / left half page"),
        ("[bold]\u2303U[/] / [bold]\u2303D[/]", "Scroll up / down half page"),
    ]),
    ("[b]Mode & Navigation[/]", [
        ("[bold]`[/]", "Toggle key-level / bitmap-level mode"),
        ("[bold]w[/] / [bold]b[/]", "Next / prev color run \u2192\u2190 (bitmap mode)"),
        ("[bold]W[/] / [bold]B[/]", "Next / prev color run \u2193\u2191 (bitmap mode)"),
        ("[bold]wasd[/]", "Switch key (key mode)"),
        ("[bold]/[/]", "Find key by name"),
        ("[bold]O[/]", "Bitmap ops popup (New / Copy / Rename / Delete)"),
        ("[bold]Tab[/]", "Show / hide cursor"),
    ]),
    ("[b]Other[/]", [
        ("[bold]?[/]", "This help"),
        ("[bold]Escape[/]", "Back"),
    ]),
]

_MAP_HELP_DATA = [
    ("[b]Navigation[/]", [
        ("[bold]wasd[/] / [bold]hjkl[/] / arrows", "Select adjacent bitmap"),
        ("[bold]^[/] / [bold]$[/]", "Leftmost / rightmost in row"),
        ("[bold]gg[/] / [bold]G[/]", "First / last row"),
        ("[bold]nG[/]", "Row n, first bitmap"),
        ("[bold]g^[/] / [bold]g$[/]", "Viewport left / right visible key"),
        ("[bold]1-9[/]", "Count prefix"),
        ("[bold]Enter[/]", "Select key & exit"),
    ]),
    ("[b]Zoom[/]", [
        ("[bold]`[/]", "Toggle zoom mode"),
        ("[bold]+=[/] / [bold]-_[/]", "Zoom in / out"),
        ("[bold]f[/] / [bold]F[/]", "Fit key / Fit all to view"),
        ("[bold]0[/]", "Reset zoom"),
    ]),
    ("[b]Pan/Scroll[/]", [
        ("[bold]~[/]", "Toggle pan/scroll mode"),
        ("[bold]hjkl[/] / arrows", "Slow pan/scroll (in Zoom mode)"),
        ("[bold]\u21e7HJKL[/] / \u21e7arrows", "Fast pan/scroll 5"),
        ("[bold]r[/]", "Reset pan/scroll"),
    ]),
    ("[b]Action[/]", [
        ("[bold]![/]", "Toggle action mode"),
        ("[bold]y[/] / [bold]Y[/]", "Yank / put yanked key"),
        ("[bold]p[/] / [bold]P[/]", "Put after / put before cursor"),
        ("[bold]d[/] / [bold]x[/]", "Delete selected key"),
    ]),
    ("[b]Find & Ops[/]", [
        ("[bold]/[/]", "Find key by name"),
        ("[bold]O[/]", "Bitmap ops popup"),
    ]),
    ("[b]Other[/]", [
        ("[bold]?[/]", "This help"),
        ("[bold]Escape[/]", "Back"),
    ]),
]

_ALL_HELP_DATA = {
    "design": _DESIGN_HELP_DATA,
    "map": _MAP_HELP_DATA,
}
_ALL_PAGES = {k: _build_pages(v) for k, v in _ALL_HELP_DATA.items()}


class HelpScreen(PopupScreen):
    """Popup listing all keybindings organized by paginated categories."""

    base_title = "Keybindings"
    _shared_page: int = 0
    CSS = """
    #hints { margin-top: 1; }
    """

    def __init__(self, mode: str = "design") -> None:
        super().__init__()
        self._mode = mode
        self._page = HelpScreen._shared_page

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(_ALL_PAGES[self._mode][0], id="content")
            yield Static("", id="hints")

    def on_mount(self) -> None:
        self._update_display()

    def _update_display(self) -> None:
        total = len(_ALL_PAGES[self._mode])
        self.query_one("#content", Static).update(_ALL_PAGES[self._mode][self._page])
        prev_is_dim = self._page == 0
        next_is_dim = self._page == total - 1

        prev_open = "[dim]" if prev_is_dim else ""
        prev_close = "[/]" if prev_is_dim else ""
        next_open = "[dim]" if next_is_dim else ""
        next_close = "[/]" if next_is_dim else ""

        self.query_one("#hints", Static).update(
            f"{prev_open}\\[b] prev{prev_close} \u2014 Page {self._page + 1}/{total} \u2014 "
            f"{next_open}\\[space] next{next_close} \\[Escape] close"
        )
        HelpScreen._shared_page = self._page

    def on_key(self, event) -> None:
        key = event.key
        ch = getattr(event, "character", None)
        total = len(_ALL_PAGES[self._mode])

        if key == "escape":
            self.dismiss(None)
            return

        if key in ("space", "j", "down", "ctrl+d"):
            if self._page < total - 1:
                self._page += 1
                self._update_display()
            return

        if key in ("b", "k", "up", "ctrl+u") or ch == "b":
            if self._page > 0:
                self._page -= 1
                self._update_display()
            return

        if key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
