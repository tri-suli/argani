"""Shared plumbing for the argani PreToolUse hooks (stdlib only)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import argani_config  # noqa: E402,F401  (re-exported for the guards)


def read_payload():
    """Parse the hook stdin JSON; return None (allow) when it is unusable."""
    try:
        payload = json.load(sys.stdin)
    except ValueError as error:
        print(f"argani hook: unreadable stdin: {error}", file=sys.stderr)
        return None
    return payload if isinstance(payload, dict) else None


def emit(payload, main_session_decision, reason):
    """Print a PreToolUse decision. Inside a subagent every match is a deny."""
    decision = "deny" if payload.get("agent_type") else main_session_decision
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))


def run_guard(guard):
    """Run guard(payload); an internal error is logged and the call is allowed."""
    payload = read_payload()
    if payload is None:
        return
    try:
        guard(payload)
    except Exception as error:  # fail open: a broken guard must not block work
        print(f"argani hook: internal error: {error!r}", file=sys.stderr)
