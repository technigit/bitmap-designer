"""Code generation and generic response screens."""
from __future__ import annotations
from typing import TYPE_CHECKING
import re
import pyperclip


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button
from textual.containers import Vertical, VerticalScroll

from ..services.codegen_service import CodegenService, STRATEGIES, FALLBACK_DEFAULT
from .popup_screen import PopupScreen

if TYPE_CHECKING:
    from ..app import BitmapDesignerApp


class CodegenScreen(PopupScreen):
    """Screen to display and copy generated JavaScript code with key filtering."""
    base_title = "Code Generation"
    CSS = """
    #code-outer { max-height: 60vh; }
    VerticalScroll { max-height: 50vh; }
    #hints { margin-top: 1; opacity: 0.5; }
    #strategy-bar { margin-top: 1; }
    #mode-bar { opacity: 0.5; }
    #keys-bar { margin-top: 1; margin-bottom: 1; }
    #status { dock: bottom; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="code-outer"):
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static("", id="strategy-bar", markup=False)
            yield Static("", id="mode-bar", markup=False)
            yield Static("", id="keys-bar", markup=False)
            yield VerticalScroll(Static("", id="code"))
            yield Static("[Enter] copy  [Escape] close", id="hints", markup=False)
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_mount(self) -> None:
        self._maximized = False
        self._refresh_all()

    def on_screen_resume(self, _event) -> None:
        self._refresh_all()

    def _page_size(self) -> int:
        margin = 3       # "  " indent
        page_info = 15   # " [Page N/M]" est.
        slot = 13        # "1:✓abcdef… " max entry width
        available = self.size.width - margin - page_info
        return max(1, min(9, available // slot))

    def _paginated_keys(self) -> tuple[list[str], int]:
        all_keys = sorted(self.app.bitmaps.keys(), key=_natural_key)
        page_size = self._page_size()
        n_pages = max(1, (len(all_keys) + page_size - 1) // page_size)
        page = min(self.app.codegen_filter_page, n_pages - 1)
        self.app.codegen_filter_page = page
        start = page * page_size
        return all_keys[start:start + page_size], n_pages

    def _keys_bar_text(self) -> str:
        all_sorted = sorted(self.app.bitmaps.keys(), key=_natural_key)
        if not all_sorted:
            return "  No bitmaps."
        page_keys, n_pages = self._paginated_keys()
        active_set = self.app.codegen_filtered_keys
        parts = []
        for i, key in enumerate(page_keys):
            in_filter = active_set is None or key in active_set
            marker = "\u2713" if in_filter else "\u2717"
            label = key if len(key) <= 8 else key[:7] + "\u2026"
            parts.append(f"{i+1}:{marker}{label}")
        page_info = f"  [Page {self.app.codegen_filter_page+1}/{n_pages}]"
        return "  " + "  ".join(parts) + page_info

    def _mode_bar_text(self) -> str:
        mode = self.app.codegen_filter_mode
        is_none = mode == "manual" and not self.app.codegen_filter_keys
        parts = []
        entries = [("all", "[A]ll"), ("current", "[C]urrent"), ("none", "[N]one")]
        for m, label in entries:
            if (m == "none" and is_none) or (m != "none" and m == mode):
                parts.append(f"*{label}")
            else:
                parts.append(label)
        parts.append("[hl/\u25c2\u25b8] page  [1-9] toggle")
        return "  " + "  ".join(parts)

    def _strategy_bar_text(self) -> str:
        strat = self.app.global_strategy.capitalize()
        label = "aximized" if self._maximized else "aximize"
        return f"  [S]trategy: {strat}  [M]{label}"

    def _apply_maximize(self) -> None:
        if self._maximized:
            self.query_one("#code-outer").styles.max_height = "100vh"
            self.query_one("#code-outer").styles.height = "100vh"
            self.query_one("#code-outer").styles.border = ("none", "transparent")
            self.query_one("#code-outer").styles.padding = (0, 2, 0, 2)
            self.query_one(VerticalScroll).styles.max_height = "100vh"
            self.query_one(VerticalScroll).styles.height = "1fr"
            self.query_one(VerticalScroll).styles.margin = (1, 0, 1, 0)
            self.query_one("#mode-bar", Static).display = False
            self.query_one("#keys-bar", Static).display = False
            self.query_one("#title", Static).styles.margin = 0
            self.query_one("#strategy-bar", Static).styles.margin = 0
            self.query_one("#hints", Static).styles.margin = 0
            self.query_one("#status", Static).styles.margin = 0
        else:
            self.query_one("#code-outer").styles.max_height = "60vh"
            self.query_one("#code-outer").styles.height = None
            self.query_one("#code-outer").styles.border = None
            self.query_one("#code-outer").styles.padding = None
            self.query_one(VerticalScroll).styles.max_height = "50vh"
            self.query_one(VerticalScroll).styles.height = None
            self.query_one(VerticalScroll).styles.margin = None
            self.query_one("#mode-bar", Static).display = True
            self.query_one("#keys-bar", Static).display = True
            self.query_one("#title", Static).styles.margin = None
            self.query_one("#strategy-bar", Static).styles.margin = None
            self.query_one("#hints", Static).styles.margin = None
            self.query_one("#status", Static).styles.margin = None

        self.query_one(VerticalScroll).scroll_home(animate=False)
        self.app.refresh(repaint=True, layout=True)

    def _refresh_all(self) -> None:
        self.query_one("#strategy-bar", Static).update(self._strategy_bar_text())
        self.query_one("#mode-bar", Static).update(self._mode_bar_text())
        self.query_one("#keys-bar", Static).update(self._keys_bar_text())
        self._generate_code()

    def _generate_code(self) -> None:
        active_filter = None if self.app.codegen_filtered_keys is None else list(self.app.codegen_filtered_keys)
        code = CodegenService(self.app.bitmaps, palette=self.app.active_palette).generate_code(keys=active_filter)
        self.query_one("#code").update(code or "No bitmap data.")
        n_keys = len(active_filter) if active_filter is not None else len(self.app.bitmaps)
        total = len(self.app.bitmaps)
        self.show_status(f"Code generated for {n_keys} of {total} keys")

    def _toggle_key_at_page_pos(self, pos: int) -> None:
        page_keys, _ = self._paginated_keys()
        if pos >= len(page_keys):
            return
        key = page_keys[pos]
        mode = self.app.codegen_filter_mode
        if mode == "manual":
            if key in self.app.codegen_filter_keys:
                self.app.codegen_filter_keys.discard(key)
            else:
                self.app.codegen_filter_keys.add(key)
        elif mode == "current":
            self.app.codegen_filter_mode = "manual"
            self.app.codegen_filter_keys = {self.app.current_key}
            if key in self.app.codegen_filter_keys:
                self.app.codegen_filter_keys.discard(key)
            else:
                self.app.codegen_filter_keys.add(key)
        else:
            self.app.codegen_filter_mode = "manual"
            self.app.codegen_filter_keys = set(self.app.bitmaps.keys())
            if key in self.app.codegen_filter_keys:
                self.app.codegen_filter_keys.discard(key)
            else:
                self.app.codegen_filter_keys.add(key)
        self._refresh_all()

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key in ("enter", "\n"):
            active_filter = None if self.app.codegen_filtered_keys is None else list(self.app.codegen_filtered_keys)
            code = CodegenService(self.app.bitmaps, palette=self.app.active_palette).generate_code(keys=active_filter)
            pyperclip.copy(code)
            self.show_status("Code copied to clipboard.")
        elif event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("j", "down"):
            event.stop()
            self.query_one(VerticalScroll).scroll_down()
        elif event.key in ("k", "up"):
            event.stop()
            self.query_one(VerticalScroll).scroll_up()
        elif event.key.lower() == "a":
            self.app.codegen_filter_mode = "all"
            self.app.codegen_filter_page = 0
            self._refresh_all()
        elif event.key.lower() == "c":
            self.app.codegen_filter_mode = "current"
            self.app.codegen_filter_page = 0
            self._refresh_all()
        elif event.key.lower() == "n":
            self.app.codegen_filter_mode = "manual"
            self.app.codegen_filter_keys = set()
            self.app.codegen_filter_page = 0
            self._refresh_all()
        elif event.key.lower() == "s":
            self.app.push_screen(StrategySelectScreen(), callback=self._on_strategy_chosen)
        elif event.key.lower() == "m":
            self._maximized = not self._maximized
            self._apply_maximize()
            self._refresh_all()
        elif event.key in ("h", "left"):
            all_keys = sorted(self.app.bitmaps.keys(), key=_natural_key)
            ps = self._page_size()
            n_pages = max(1, (len(all_keys) + ps - 1) // ps)
            if self.app.codegen_filter_page > 0:
                self.app.codegen_filter_page -= 1
            else:
                self.app.codegen_filter_page = n_pages - 1
            self._refresh_all()
        elif event.key in ("l", "right"):
            all_keys = sorted(self.app.bitmaps.keys(), key=_natural_key)
            ps = self._page_size()
            n_pages = max(1, (len(all_keys) + ps - 1) // ps)
            if self.app.codegen_filter_page < n_pages - 1:
                self.app.codegen_filter_page += 1
            else:
                self.app.codegen_filter_page = 0
            self._refresh_all()
        elif event.key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._toggle_key_at_page_pos(int(event.key) - 1)

    def _on_strategy_chosen(self, strategy: str | None) -> None:
        if strategy:
            self.app.set_global_strategy(strategy)
            self._refresh_all()


class StrategySelectScreen(PopupScreen):
    """Screen to select the code generation strategy."""
    base_title = "Code Generation Strategy"
    CSS = """
    #strategy-outer { max-height: 60vh; }
    #menu { margin-top: 1; margin-bottom: 1; }
    #hints { margin-top: 1; opacity: 0.5; }
    #status { dock: bottom; }
    """

    def _strategy_text(self) -> str:
        current = self.app.get_codegen_strategy()
        lines = [f"  Bitmap \"{self.app.current_key}\":"]
        for s in STRATEGIES:
            marker = "◄" if s == current else " "
            default_mark = "  (default)" if s == FALLBACK_DEFAULT else ""
            lines.append(f"  [{s[0].upper()}] {s.capitalize():10s} {marker}{default_mark}")
        return "\n".join(lines)

    def compose(self) -> ComposeResult:
        with Vertical(id="strategy-outer"):
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static("", id="menu", markup=False)
            yield Static("[?] details  [S]tats  [Enter] save  [Escape] cancel", id="hints", markup=False)
            yield Static("", id="status")

    def on_mount(self) -> None:
        self._refresh()

    def on_screen_resume(self, _event) -> None:
        self._refresh()

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _refresh(self):
        self.query_one("#menu", Static).update(self._strategy_text())

    def _select(self, strategy: str) -> None:
        self.app.set_codegen_strategy(strategy)
        self.dismiss(strategy)

    def _show_details(self) -> None:
        self.app.push_screen(StrategyDetailsScreen())

    def _on_stats_chosen(self, strategy: str | None) -> None:
        if strategy is not None:
            self.app.set_codegen_strategy(strategy)
            self._refresh()

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        k = event.key.lower()
        if k == "f":
            self._select("fast")
        elif k == "b":
            self._select("balanced")
        elif k == "t":
            self._select("thorough")
        elif k == "o":
            self._select("optimal")
        elif k in ("enter", "\n"):
            current = self.app.get_codegen_strategy()
            self.dismiss(current)
        elif k == "escape":
            self.dismiss(None)
        elif k in ("question_mark", "slash"):
            self._show_details()
        elif k == "s":
            self.app.push_screen(StatsPopupScreen(), callback=self._on_stats_chosen)


class StrategyDetailsScreen(PopupScreen):
    """Screen showing strategy descriptions."""
    base_title = "Strategy Details"
    def compose(self) -> ComposeResult:
        details = (
            "Fast — Histogram maximal-rectangle algorithm with post-merge."
            " Least optimal but fast.\n"
            "\n"
            "Balanced — Row-scan greedy extraction with post-merge."
            " Best general-purpose tradeoff. (default)\n"
            "\n"
            "Thorough — Decomposes connected components first, then"
            " extracts per component. Better for disjoint shapes.\n"
            "\n"
            "Optimal — Runs Balanced and Thorough, picks the result"
            " with fewer rectangles.\n"
        )
        with Vertical():
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static(details, id="details", markup=False)
            yield Static("[Escape] close", id="hints", markup=False)
            yield Static("", id="status")

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key in ("enter", "\n", "escape"):
            self.app.pop_screen()

class StatsPopupScreen(PopupScreen):
    base_title = "Code Generation Statistics"
    CSS = """
    #stats-outer { max-height: 60vh; }
    #stats-outer VerticalScroll { max-height: 50vh; }
    #stats-header { margin-top: 1; }
    #stats-footer { margin-top: 1; }
    """

    def __init__(self, keys: set[str] | None = None):
        super().__init__()
        self._show_detail = True
        self._group_by_bitmap = False
        self._keys = keys

    def compose(self) -> ComposeResult:
        with Vertical(id="stats-outer"):
            yield Static(self.app.title_with_file(self.base_title), id="title")
            yield Static("", id="stats-header", markup=False)
            yield VerticalScroll(Static("", id="stats-rows", markup=False))
            yield Static("", id="stats-footer", markup=False)
            yield Static("[fbto] select  [D] detail  [G] by bitmap  [Escape] close", id="hints", markup=False)
            yield Static("", id="status")

    def on_mount(self) -> None:
        self._refresh()

    def show_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _refresh(self) -> None:
        try:
            keys_list = list(self._keys) if self._keys is not None else None
            all_stats = CodegenService.generate_all_strategy_stats(
                self.app.bitmaps, palette=self.app.active_palette, keys=keys_list
            )

            if self._group_by_bitmap:
                header = (
                    f"  {'Bitmap':<16} {'Rects':>6}  {'Cells/rect':>10}  {'Score':>6}\n"
                    f"  {'-'*16} {'-'*6}  {'-'*10}  {'-'*6}"
                )
                all_bm_keys: set[str] = set()
                for strategy in STRATEGIES:
                    all_bm_keys.update(all_stats[strategy].get("per_bitmap", {}).keys())
                bm_best_score: dict[str, float] = {}
                for bm_key in all_bm_keys:
                    best = 0.0
                    for strategy in STRATEGIES:
                        per_bm = all_stats[strategy].get("per_bitmap", {})
                        if bm_key in per_bm:
                            s_val = per_bm[bm_key].get("score", 0.0)
                            if s_val > best:
                                best = s_val
                    bm_best_score[bm_key] = best
                sorted_bitmaps = sorted(all_bm_keys, key=lambda k: bm_best_score[k], reverse=True)

                rows = []
                for idx, bm_key in enumerate(sorted_bitmaps):
                    if idx > 0:
                        rows.append("")
                    rows.append(f"  {bm_key}")
                    if self._show_detail:
                        best_for_bm = max(
                            all_stats[s].get("per_bitmap", {}).get(bm_key, {}).get("score", 0.0)
                            for s in STRATEGIES
                        )
                        for strategy in STRATEGIES:
                            per_bm = all_stats[strategy].get("per_bitmap", {})
                            if bm_key not in per_bm:
                                continue
                            bm_stats = per_bm[bm_key]
                            bs = bm_stats["score"]
                            bs_s = f"{bs:.1f}%" if bs != int(bs) else f"{int(bs)}%"
                            cpr = bm_stats["cells_per_rect"]
                            cpr_s = f"{cpr:.1f}" if cpr != int(cpr) else str(int(cpr))
                            marker = "*" if bs == best_for_bm else " "
                            rows.append(
                                f"    {marker} {strategy.capitalize():<12} {bm_stats['rects']:>6}  {cpr_s:>10}  {bs_s:>6}"
                            )
                    else:
                        best_for_bm = max(
                            all_stats[s].get("per_bitmap", {}).get(bm_key, {}).get("score", 0.0)
                            for s in STRATEGIES
                        )
                        best_strats = [
                            s for s in STRATEGIES
                            if all_stats[s].get("per_bitmap", {}).get(bm_key, {}).get("score", 0.0) == best_for_bm
                        ]
                        best_strat = best_strats[0]
                        best_stats = all_stats[best_strat].get("per_bitmap", {}).get(bm_key, {})
                        bs = best_stats["score"]
                        bs_s = f"{bs:.1f}%" if bs != int(bs) else f"{int(bs)}%"
                        cpr = best_stats["cells_per_rect"]
                        cpr_s = f"{cpr:.1f}" if cpr != int(cpr) else str(int(cpr))
                        rows.append(
                            f"    * {best_strat.capitalize():<12} {best_stats['rects']:>6}  {cpr_s:>10}  {bs_s:>6}"
                        )
                self.query_one("#hints", Static).update(
                    "[fbto] select  [D] detail  [G]rouping by bitmap  [Escape] close"
                )
            else:
                header = (
                    f"  {'Strategy':<16} {'Rects':>6}  {'Cells/rect':>10}  {'Score':>6}\n"
                    f"  {'-'*16} {'-'*6}  {'-'*10}  {'-'*6}"
                )
                sorted_strategies = sorted(
                    STRATEGIES,
                    key=lambda s: all_stats[s].get("overall_score", 0),
                    reverse=True,
                )
                best_score = max(
                    all_stats[s].get("overall_score", 0) for s in STRATEGIES
                )

                rows = []
                for idx, strategy in enumerate(sorted_strategies):
                    if idx > 0:
                        rows.append("")
                    s = all_stats[strategy]
                    score = s.get("overall_score", 0)
                    rects = s.get("total_rects", 0)
                    score_s = f"{score:.1f}%" if score != int(score) else f"{int(score)}%"
                    marker = "*" if score == best_score else " "
                    rows.append(
                        f"  {marker} {strategy.capitalize():<14} {rects:>6}  {s['overall_cells_per_rect']:>10}  {score_s:>6}"
                    )
                    if self._show_detail:
                        per_bitmap = s.get("per_bitmap", {})
                        for bm_key, bm_stats in per_bitmap.items():
                            bs = bm_stats["score"]
                            bs_s = f"{bs:.1f}%" if bs != int(bs) else f"{int(bs)}%"
                            cpr = bm_stats["cells_per_rect"]
                            cpr_s = f"{cpr:.1f}" if cpr != int(cpr) else str(int(cpr))
                            rows.append(
                                f"      {bm_key:<12.12} {bm_stats['rects']:>6}  {cpr_s:>10}  {bs_s:>6}"
                            )
                self.query_one("#hints", Static).update(
                    "[fbto] select  [D] detail  [G]rouping by strategy  [Escape] close"
                )

            self.query_one("#stats-header", Static).update(header)
            self.query_one("#stats-rows", Static).update("\n".join(rows))
        except Exception as e:
            self.show_status(f"Error: {e}")

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.show_status("")
            self.app.refresh(repaint=True, layout=True)
            return
        k = event.key.lower()
        if k in ("enter", "\n", "escape"):
            self.dismiss(None)
        elif k in ("j", "down"):
            event.stop()
            self.query_one(VerticalScroll).scroll_down()
        elif k in ("k", "up"):
            event.stop()
            self.query_one(VerticalScroll).scroll_up()
        elif k == "d":
            self._show_detail = not self._show_detail
            self._refresh()
        elif k == "g":
            self._group_by_bitmap = not self._group_by_bitmap
            self._refresh()
        elif k == "f":
            self.app.set_codegen_strategy("fast")
            self.dismiss("fast")
        elif k == "b":
            self.app.set_codegen_strategy("balanced")
            self.dismiss("balanced")
        elif k == "t":
            self.app.set_codegen_strategy("thorough")
            self.dismiss("thorough")
        elif k == "o":
            self.app.set_codegen_strategy("optimal")
            self.dismiss("optimal")


class ResponseScreen(Screen):
    """Generic message screen with an OK button."""

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Static("Message", id="title")
        with Vertical():
            yield Static(self.message, id="message")
            yield Button("OK", id="ok")

    def on_button_pressed(self, event) -> None:
        if event.button.id == "ok":
            self.app.pop_screen()

    def on_key(self, event) -> None:
        if event.key == "ctrl+l":
            self.app.refresh(repaint=True, layout=True)
            return
        if event.key == "escape":
            self.app.pop_screen()
        elif event.key in ("enter", "\n"):
            self.app.pop_screen()
