"""Named values the office backend compares against or decides by; one place, so no module holds a magic literal."""

import re
from http import HTTPStatus
from pathlib import Path

# --- plugin location -------------------------------------------------------------------------------------------
SCRIPTS_DIR_ENV_VAR = "ARGANI_SCRIPTS_DIR"

DEFAULT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "argani" / "scripts"

PLUGIN_MODULE_NAMES = ("argani_config", "argani_home", "board", "factory_state", "project_registry")

NEEDS_HUMAN_COLUMN_INDEX = -1  # board.COLUMNS ends with the "Needs human" column

# --- command line ----------------------------------------------------------------------------------------------
PORT_ENV_VAR = "OFFICE_BACKEND_PORT"

DEFAULT_HOST = "127.0.0.1"

DEFAULT_PORT = 2212

MIN_PORT = 1

MAX_PORT = 65535

EXIT_SUCCESS = 0

EXIT_INVALID_CONFIGURATION = 2

# --- HTTP ------------------------------------------------------------------------------------------------------
BOARD_PATH = "/api/board"

TASKS_ROUTE_SEGMENTS = ("", "api", "tasks")  # a split "/api/tasks/..." path starts with these

TASK_DETAIL_SEGMENT_COUNT = 2  # project, slug

TASK_FILE_SEGMENT_COUNT = 3  # project, slug, "file"

TASK_FILE_ACTION_INDEX = 2

TASK_FILE_ACTION = "file"

FILE_PATH_PARAMETER = "path"

JSON_TYPE = "application/json; charset=utf-8"

TEXT_TYPE = "text/plain; charset=utf-8"

ALLOWED_METHODS = "GET, HEAD"

ALLOWED_HOSTS = ("localhost", "127.0.0.1", "::1")

HOST_HEADER = "Host"

ALLOW_HEADER = "Allow"

CONTENT_TYPE_HEADER = "Content-Type"

CONTENT_LENGTH_HEADER = "Content-Length"

CACHE_CONTROL_HEADER = "Cache-Control"

CONTENT_TYPE_OPTIONS_HEADER = "X-Content-Type-Options"

NO_STORE = "no-store"

NO_SNIFF = "nosniff"

STATUS_OK = HTTPStatus.OK

STATUS_BAD_REQUEST = HTTPStatus.BAD_REQUEST

STATUS_FORBIDDEN = HTTPStatus.FORBIDDEN

STATUS_NOT_FOUND = HTTPStatus.NOT_FOUND

STATUS_METHOD_NOT_ALLOWED = HTTPStatus.METHOD_NOT_ALLOWED

STATUS_PAYLOAD_TOO_LARGE = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

STATUS_INTERNAL_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR

# --- tasks -----------------------------------------------------------------------------------------------------
BYTES_PER_MEGABYTE = 1024 * 1024

MAX_FILE_MEGABYTES = 2

MAX_FILE_BYTES = MAX_FILE_MEGABYTES * BYTES_PER_MEGABYTE

MR_FILE = "mr.md"

MR_LINE = re.compile(r"^MR:.*?(https?://\S+)", re.MULTILINE)

MR_URL_TRAILING_CHARACTERS = ")>"

NUL_CHARACTER = "\0"

STAGE_DONE = "done"

STAGE_ERROR = "error"

VERDICT_PASS = "PASS"

VERDICT_CHANGES = "CHANGES"

VERDICT_APPROVE = "APPROVE"

VERDICT_ESCALATE = "ESCALATE"

VERDICT_INVALID = "INVALID"

REVIEW_PENDING = "pending"

REVIEW_INVALID = "invalid"

# --- job files -------------------------------------------------------------------------------------------------
JOB_FILE_ORDER = ("intent.md", "spec.md", "plan.md", "build.md", "decision.md", "mr-body.md", MR_FILE)

CHANGE_DIFF_FILE = "change.diff"

REVIEW_FILE_PREFIX = "review-"

MARKDOWN_SUFFIX = ".md"

PATH_SEPARATOR = "/"

ROUND_PATH = re.compile(r"review/round-(\d+)/")

JOB_FILES_RANK = 0  # job files sort before the files of the review rounds

ROUND_FILES_RANK = 1

NO_ROUND_NUMBER = 0

REVIEW_FILE_KIND = 0  # inside a round: reviews, then the change under review, then anything else

CHANGE_FILE_KIND = 1

OTHER_FILE_KIND = 2

GROUP_JOB = "Job"

ROUND_GROUP_TEMPLATE = "Round {number}"

TONE_GOOD = "good"

TONE_WARN = "warn"

TONE_STOP = "stop"

TONES = {VERDICT_PASS: TONE_GOOD, VERDICT_APPROVE: TONE_GOOD, VERDICT_CHANGES: TONE_WARN,
         VERDICT_ESCALATE: TONE_STOP}

FIRST_LINE_LIMIT = 200

PREVIEW_BYTES = 4096

BYTE_ORDER_MARK = "﻿"

ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# --- usage events ----------------------------------------------------------------------------------------------
EVENT_FILE_PATTERN = "*.jsonl"

FINISH_EVENT = "finish"

MIN_COUNT = 0

TOKEN_FIELDS = (("input", "input_tokens"), ("output", "output_tokens"),
                ("cacheCreation", "cache_creation_input_tokens"), ("cacheRead", "cache_read_input_tokens"))
