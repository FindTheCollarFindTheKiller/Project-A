#!/usr/bin/env python3
"""
Nation Forge — Country Governance Simulation
Entry point: python main.py
"""
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

# Force UTF-8 output on Windows so Rich can render Unicode box/block characters.
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from simulation.ui.cli import run_cli

if __name__ == "__main__":
    run_cli()
