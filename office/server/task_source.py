"""Where the office gets tasks, their files and their usage from."""

import importlib
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import job_files
import usage_events
from board_source import ensure_importable
from constants import (
    DEFAULT_SCRIPTS_DIR, MAX_FILE_BYTES, MR_FILE, MR_LINE, MR_URL_TRAILING_CHARACTERS,
    NUL_CHARACTER, PLUGIN_MODULE_NAMES, REVIEW_INVALID, REVIEW_PENDING, SCRIPTS_DIR_ENV_VAR,
    STAGE_ERROR, STATUS_BAD_REQUEST, STATUS_INTERNAL_ERROR, STATUS_NOT_FOUND, STATUS_PAYLOAD_TOO_LARGE,
    VERDICT_INVALID,
)


class TaskSourceError(Exception):
    status = STATUS_INTERNAL_ERROR


class BadRequest(TaskSourceError):
    status = STATUS_BAD_REQUEST


class NotFound(TaskSourceError):
    status = STATUS_NOT_FOUND


class FileTooLarge(TaskSourceError):
    status = STATUS_PAYLOAD_TOO_LARGE


class TaskSource(Protocol):
    def list_tasks(self) -> list:
        """A summary of every task of every registered project."""

    def task_detail(self, project: str, slug: str) -> dict:
        """The summary of one task plus stage, files and so on; raises TaskSourceError."""

    def read_file(self, project: str, slug: str, path: str) -> str:
        """The text of one listed file of a task; raises TaskSourceError."""


class PluginTaskSource:
    """Builds tasks with the argani plugin's own scripts, so the schema and the stage rules never fork."""

    def __init__(self, scripts_dir=None, usage_reader=None):
        self.usage_reader = usage_reader or usage_events.UsageReader()

        raw = scripts_dir or os.environ.get(SCRIPTS_DIR_ENV_VAR)

        self.scripts_dir = Path(raw) if raw else DEFAULT_SCRIPTS_DIR

    def _plugin(self):
        ensure_importable(self.scripts_dir)

        return {name: importlib.import_module(name)
                for name in PLUGIN_MODULE_NAMES}

    def list_tasks(self):
        plugin = self._plugin()

        home = plugin["argani_home"].home_path()

        usage = self.usage_reader.usage_by_task(home / plugin["argani_home"].EVENTS_DIR)

        tasks = []

        for entry in plugin["project_registry"].list_projects(home):
            name = entry["name"]

            config, config_error = self._load_config(plugin, home, name)

            for row in plugin["board"].project_tasks(home, entry, datetime.now(timezone.utc)):
                summary, _, _ = self._summarize(plugin, home, name, row["slug"], config, config_error, usage)

                tasks.append(summary)

        return tasks

    def task_detail(self, project, slug):
        plugin = self._plugin()

        home = plugin["argani_home"].home_path()

        job_dir = self._job_dir(plugin, home, project, slug)

        config, config_error = self._load_config(plugin, home, project)

        usage = self.usage_reader.usage_by_task(home / plugin["argani_home"].EVENTS_DIR)

        summary, state, error = self._summarize(plugin, home, project, slug, config, config_error, usage)

        board = plugin["board"]

        if state is None:
            extra = {"next": str(error), "column": board.NEEDS_HUMAN, "reviewers": [],
                     "models": None, "decision": None}
        else:
            extra = {"next": state["next"], "column": state["column"],
                     "reviewers": state["reviewers"], "models": state["models"], "decision": state["decision"]}

        return {**summary, **extra, "files": job_files.describe_files(job_dir)}

    def read_file(self, project, slug, path):
        plugin = self._plugin()

        home = plugin["argani_home"].home_path()

        job_dir = self._job_dir(plugin, home, project, slug)

        if NUL_CHARACTER in path or path not in set(job_files.regular_files(job_dir)):
            raise NotFound("file not found")

        # shortcut: the folders above the file can still be swapped for symlinks between the listing and the
        # open; only the last component is guarded. Upgrade to openat(dir_fd) with O_NOFOLLOW per component if
        # the home ever holds untrusted writers.
        try:
            descriptor = os.open(job_dir / path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise NotFound("file not found")

        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(descriptor)

            if not stat.S_ISREG(info.st_mode):
                raise NotFound("file not found")

            if info.st_size > MAX_FILE_BYTES:
                raise FileTooLarge(f"file is larger than {MAX_FILE_BYTES} bytes")

            data = handle.read(MAX_FILE_BYTES + 1)  # the file may have grown since fstat

        if len(data) > MAX_FILE_BYTES:
            raise FileTooLarge(f"file is larger than {MAX_FILE_BYTES} bytes")

        return data.decode("utf-8", errors="replace")

    def _job_dir(self, plugin, home, project, slug):
        if not plugin["project_registry"].PROJECT_NAME.fullmatch(project):
            raise BadRequest("invalid project name")

        if not plugin["argani_config"].SLUG_PATTERN.fullmatch(slug):
            raise BadRequest("invalid slug")

        if project not in {entry["name"] for entry in plugin["project_registry"].list_projects(home)}:
            raise NotFound("project not found")

        job_dir = plugin["board"].tasks_folder(home, project) / slug

        if job_dir.is_symlink() or not job_dir.is_dir():
            raise NotFound("task not found")

        return job_dir

    @staticmethod
    def _load_config(plugin, home, name):
        try:
            return plugin["argani_config"].load_project_config(home, name), None
        except (ValueError, OSError) as error:
            return None, error

    def _summarize(self, plugin, home, project, slug, config, config_error, usage):
        """(summary, state, error); state is None and error says why when the state cannot be built."""

        job_dir = plugin["board"].tasks_folder(home, project) / slug

        state, error = None, config_error

        if error is None:
            try:
                state = plugin["factory_state"].build_state(slug, config=config)

                if state is None:
                    error = ValueError("job folder not found")
            except (ValueError, OSError) as failure:
                state, error = None, failure

        summary = {
            "project": project, "slug": slug,
            "stage": state["stage"] if state else STAGE_ERROR,
            "risk": state["risk"] if state else None,
            "round": state["round"] if state else 0,
            "rounds": self._rounds(state) if state else [],
            "mrUrl": self._mr_url(job_dir),
            "updatedAt": job_files.newest_modification(job_dir),
            **usage.get((project, slug), usage_events.empty_usage()),
        }

        return summary, state, error

    @staticmethod
    def _rounds(state):
        """Per round {reviewer: PASS | CHANGES | invalid | pending}, from the plugin's own verdict semantics."""

        return [{"n": entry["n"],
                 "reviews": {name: REVIEW_PENDING if name not in entry["complete"]
                             else REVIEW_INVALID if entry["verdicts"][name] == VERDICT_INVALID
                             else entry["verdicts"][name]
                             for name in entry["expected"]}}
                for entry in state["rounds"]]

    @staticmethod
    def _mr_url(job_dir):
        try:
            text = (job_dir / MR_FILE).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        match = MR_LINE.search(text)

        return match.group(1).rstrip(MR_URL_TRAILING_CHARACTERS) if match else None
