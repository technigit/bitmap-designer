"""Help screen showing all keybindings."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from .popup_screen import PopupScreen


class HelpScreen(PopupScreen):
    """Popup listing all keybindings organized by category."""

    base_title = "Keybindings"
    CSS = """
    #hints { margin-top: 1; opacity: 0.5; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(
                "  [b]Movement[/]\n"
                "    [bold]h[/][dim]j[/][bold]k[/][dim]l[/] / arrows  Move cursor (or scroll in scroll mode)\n"
                "    [bold]^[/]          First non-empty pixel / first key\n"
                "    [bold]$[/]          Last column / last key\n"
                "    [bold]0[/]          Column 0 / first key\n"
                "    [bold]G[/]          Last line / last key\n"
                "    [bold]g[/][dim]g[/]          First line / first key\n"
                "    [bold]Enter[/]      Beginning of next line\n"
                "  [b]Editing[/]\n"
                "    [bold]space[/]      Paint pixel at cursor (advances)\n"
                "    [bold]x[/]          Delete pixel at cursor\n"
                "    [bold]D[/]          Delete current row\n"
                "    [bold]d[/][dim]d[/]          Delete N rows (with count prefix)\n"
                "    [bold]e[/]          Eyedropper — pick color under cursor\n"
                "    [bold]F[/]          Flood fill\n"
                "    [bold]R[/]          Rectangle mode\n"
                "  [b]Visual / Yank / Paste[/]\n"
                "    [bold]v[/]          Start visual selection\n"
                "    [bold]y[/]          Yank line\n"
                "    [bold]y[/][dim]y[/]          Yank current row\n"
                "    [bold]p[/]          Paste clipboard at cursor\n"
                "    [bold]⇧P[/]          Preview HTML\n"
                "  [b]Repeat[/]\n"
                "    [bold].[/]           Repeat last action\n"
                "  [b]Count Prefix[/]\n"
                "    [bold]1[/][dim]–[/][bold]9[/]        Prefix for count (e.g. [bold]5[/][dim]G[/] → line 5)\n"
                "  [b]Mode & Display[/]\n"
                "    [bold]`[/]          Toggle key-level / bitmap-level mode\n"
                "    [bold]\\[/]         Toggle scroll mode\n"
                "  [b]Navigation[/]\n"
                "    [bold]w[/][dim]a[/][bold]s[/][dim]d[/]        Switch key (key mode)\n"
                "    [bold]w[/]          Next color run \u2192 (bitmap mode)\n"
                "    [bold]W[/]          Next color run \u2193 (bitmap mode)\n"
                "    [bold]b[/]          Prev color run \u2190 (bitmap mode)\n"
                "    [bold]B[/]          Prev color run \u2191 (bitmap mode)\n"
                "    [bold]b[/]          Bitmap ops popup (key mode)\n"
                "    [bold]⇧O[/]          Bitmap ops popup (New/Copy/Rename/Delete)\n"
                "    [bold]/[/]          Find key by name\n"
                "    [bold]Tab[/]        Show / hide cursor\n"
                "  [b]Other[/]\n"
                "    [bold]C[/]          Color picker\n"
                "    [bold]M[/]          Map / remap\n"
                "    [bold]U[/]          Undo\n"
                "    [bold]⌃[/][bold]R[/]      Redo\n"
                "    [bold]?[/]          This help\n"
                "    [bold]Escape[/]     Back\n",
                markup=False,
            )
            yield Static("[Escape] close", id="hints", markup=False)

    def on_key(self, event) -> None:
        if event.key in ("escape", "?"):
            self.dismiss(None)
        elif event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
