"""Helpers for running the hook scripts as Claude Code does: JSON on stdin, decision on stdout."""
import json
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"


def run_hook(script, payload):
    """Run hooks/<script> with payload on stdin; return the decision dict or None (allow)."""
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=json.dumps(payload), capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]


def decision_of(output):
    return output["permissionDecision"] if output else None


def bash_payload(command, cwd, agent_type=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(cwd),
               "tool_input": {"command": command, "description": "test"}}
    if agent_type:
        payload["agent_type"] = agent_type
    return payload


def file_payload(tool_name, cwd, file_path, agent_type=None, **tool_input):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "cwd": str(cwd),
               "tool_input": {"file_path": str(file_path), **tool_input}}
    if agent_type:
        payload["agent_type"] = agent_type
    return payload
