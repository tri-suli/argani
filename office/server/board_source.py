"""Where the office gets the board snapshot from."""
import os
import sys
from pathlib import Path
from typing import Protocol

SCRIPTS_DIR_ENV_VAR = "ARGANI_SCRIPTS_DIR"
DEFAULT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "argani" / "scripts"


class BoardSource(Protocol):
    def snapshot(self) -> dict:
        """The current board as a JSON-serialisable dict."""


class PluginBoardSource:
    """Reads the board through the argani plugin's own board.py, so the schema never forks."""

    def __init__(self, scripts_dir=None):
        raw = scripts_dir or os.environ.get(SCRIPTS_DIR_ENV_VAR)
        self.scripts_dir = Path(raw) if raw else DEFAULT_SCRIPTS_DIR

    def snapshot(self) -> dict:
        # the plugin modules import each other by plain name, so the folder must be importable
        if str(self.scripts_dir) not in sys.path:
            sys.path.insert(0, str(self.scripts_dir))
        import argani_home
        import board
        return board.board(argani_home.home_path())
