"""Centered modal popup base class for dialog screens."""
from textual.screen import ModalScreen


class PopupScreen(ModalScreen):
    """A centered modal popup that dims the underlying screen."""
    DEFAULT_CSS = """
    PopupScreen {
        align: center middle;
    }

    PopupScreen > * {
        width: auto;
    }

    PopupScreen > Vertical {
        border: thick $primary;
        width: 80%;
        min-width: 40;
        max-width: 80;
        height: auto;
        padding: 0 2 1 2;
        background: $surface;
    }

    PopupScreen #status { margin-top: 1; }
    """
