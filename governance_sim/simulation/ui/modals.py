"""
Reusable Textual modal widgets shared across the TUI screens.

These replace the old Rich `Prompt.ask` / `Confirm.ask` blocking calls with
mouse-clickable (and keyboard-operable) modal dialogs.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple, Any

from rich.console import Group, RenderableType
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from . import display as _display_mod


def capture_render(fn, *args, **kwargs) -> RenderableType:
    """Call a `display.print_*` function while capturing everything it would
    have printed to the Rich console, returning it as a single renderable.

    This lets the Textual UI reuse all of the existing dashboard/report
    formatting logic in `display.py` unchanged.
    """

    class _Capture:
        def __init__(self) -> None:
            self.items: List[RenderableType] = []

        def print(self, *p_args, **_p_kwargs) -> None:
            self.items.extend(p_args)

        def clear(self) -> None:
            pass

    original = _display_mod.console
    cap = _Capture()
    _display_mod.console = cap
    try:
        fn(*args, **kwargs)
    finally:
        _display_mod.console = original
    return Group(*cap.items)


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation dialog. Dismisses with a bool."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    ConfirmModal > Container {
        width: auto;
        max-width: 70%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }
    ConfirmModal Horizontal {
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    ConfirmModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str, *, default: bool = True) -> None:
        super().__init__()
        self._message = message
        self._default = default

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._message)
            with Horizontal():
                yield Button("Yes", id="yes", variant="success")
                yield Button("No", id="no", variant="error")

    @on(Button.Pressed, "#yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def _no(self) -> None:
        self.dismiss(False)


class ChoiceModal(ModalScreen[Optional[Any]]):
    """A clickable list of labelled choices. Dismisses with the chosen value,
    or None if cancelled/backed out."""

    DEFAULT_CSS = """
    ChoiceModal {
        align: center middle;
    }
    ChoiceModal > VerticalScroll {
        width: auto;
        min-width: 50%;
        max-width: 90%;
        max-height: 80%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }
    ChoiceModal Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str, options: Iterable[Tuple[str, Any]], *, allow_cancel: bool = True) -> None:
        super().__init__()
        self._title = title
        self._options = list(options)
        self._allow_cancel = allow_cancel

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self._title, classes="title")
            for i, (label, _value) in enumerate(self._options):
                yield Button(label, id=f"opt-{i}")
            if self._allow_cancel:
                yield Button("← Back", id="cancel", variant="default")

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "cancel":
            self.dismiss(None)
            return
        if button_id.startswith("opt-"):
            idx = int(button_id.split("-", 1)[1])
            self.dismiss(self._options[idx][1])


class InputModal(ModalScreen[Optional[str]]):
    """A single-line text input dialog. Dismisses with the entered string,
    or None if cancelled."""

    DEFAULT_CSS = """
    InputModal {
        align: center middle;
    }
    InputModal > Container {
        width: auto;
        min-width: 50%;
        max-width: 90%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }
    InputModal Horizontal {
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    InputModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, prompt: str, *, default: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self._prompt)
            yield Input(value=self._default, id="value")
            with Horizontal():
                yield Button("OK", id="ok", variant="success")
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        self.query_one("#value", Input).focus()

    @on(Input.Submitted)
    def _submitted(self) -> None:
        self.dismiss(self.query_one("#value", Input).value)

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(self.query_one("#value", Input).value)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class InfoModal(ModalScreen[None]):
    """Displays a Rich renderable (e.g. from `capture_render`) with a Close
    button. Used for reports, dashboards, and detail views."""

    DEFAULT_CSS = """
    InfoModal {
        align: center middle;
    }
    InfoModal > VerticalScroll {
        width: 92%;
        height: 90%;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }
    InfoModal Button {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, renderable: RenderableType, *, title: str = "") -> None:
        super().__init__()
        self._renderable = renderable
        self._title = title

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            if self._title:
                yield Label(self._title, classes="title")
            yield Static(self._renderable)
            yield Button("Close", id="close", variant="primary")

    @on(Button.Pressed, "#close")
    def _close(self) -> None:
        self.dismiss(None)
