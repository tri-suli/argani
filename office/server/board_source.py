"""Where the office gets the board snapshot from."""
import os
import sys
from pathlib import Path
from typing import Protocol

SCRIPTS_DIR_ENV_VAR = "ARGANI_SCRIPTS_DIR"
DEFAULT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "argani" / "scripts"


def ensure_importable(scripts_dir):
    """The plugin modules import each other by plain name, so their folder must be importable."""
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


class BoardSource(Protocol):
    def snapshot(self) -> dict:
        """The current board as a JSON-serialisable dict."""


class PluginBoardSource:
    """Reads the board through the argani plugin's own board.py, so the schema never forks."""

    def __init__(self, scripts_dir=None):
        raw = scripts_dir or os.environ.get(SCRIPTS_DIR_ENV_VAR)
        self.scripts_dir = Path(raw) if raw else DEFAULT_SCRIPTS_DIR

    def snapshot(self) -> dict:
        ensure_importable(self.scripts_dir)
        import argani_home
        import board
        return board.board(argani_home.home_path())
