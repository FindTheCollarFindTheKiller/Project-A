"""Shared filesystem paths that work both from source and inside a frozen exe."""
from __future__ import annotations

import os
import sys


def app_base_dir() -> str:
    """Base directory for user-writable data (saves, screenshots).

    When running as a PyInstaller-frozen executable, __file__-relative paths
    resolve into the temporary extraction folder, which is wiped on exit.
    Use the executable's own directory instead so data persists across runs.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # governance_sim/simulation/paths.py -> governance_sim/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def saves_dir() -> str:
    return os.path.join(app_base_dir(), "saves")
