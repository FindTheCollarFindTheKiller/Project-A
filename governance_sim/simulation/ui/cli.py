"""
Entry point for the Nation Forge terminal UI.

The interactive game loop now runs on Textual (see `tui.py`), which gives
every menu, policy screen, and dialog full mouse support in addition to
keyboard navigation.
"""
from __future__ import annotations

from .tui import run_tui


def run_cli() -> None:
    run_tui()
