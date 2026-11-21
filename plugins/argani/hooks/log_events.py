#!/usr/bin/env python3
"""Append-only event log of the argani agents: one JSON line per event in <home>/events/<date>.jsonl.

Observes only: prints nothing, always exits 0, errors go to stderr. Without a home it does nothing.
"""
import json
import re
import sys
from datetime import datetime, timezone

from hook_common import argani_config, read_payload  # noqa: F401  (hook_common sets up sys.path)

import argani_home  # noqa: E402
import project_registry  # noqa: E402

JOB_PATH = re.compile(r"(?:Slug folder|Intent):\s*[`'\"]?([^\s`'\"]+)")
LAST_MESSAGE_LIMIT = 500
USAGE_COUNTS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def mapping(value):
    return value if isinstance(value, dict) else {}


def text(value):
    return value if isinstance(value, str) else ""


def job_of(prompt):
    """(project, slug) of the first job path in an agent prompt; (None, None) when none resolves."""
    home = argani_home.home_path()
    for match in JOB_PATH.finditer(text(prompt)):
        found = project_registry.project_of_path(match.group(1), home)
        if found and len(found[1].parts) >= 2 and found[1].parts[0] == "tasks":
            return found[0], found[1].parts[1]
    return None, None


def spawn(payload):
    tool_input = mapping(payload.get("tool_input"))
    project, slug = job_of(tool_input.get("prompt"))
    return {"tool_use_id": payload.get("tool_use_id"), "model": tool_input.get("model"),
            "project": project, "slug": slug, "cwd": payload.get("cwd")}


def start(payload):
    return {"agent_id": payload.get("agent_id")}


def stop(payload):
    return {"agent_id": payload.get("agent_id"), "agent_transcript_path": payload.get("agent_transcript_path"),
            "last_assistant_message": text(payload.get("last_assistant_message"))[:LAST_MESSAGE_LIMIT]}


def finish(payload):
    response = mapping(payload.get("tool_response"))
    project, slug = job_of(mapping(payload.get("tool_input")).get("prompt"))
    fields = {"tool_use_id": payload.get("tool_use_id"), "agent_id": response.get("agentId"),
              "status": response.get("status"), "duration_ms": payload.get("duration_ms"),
              "project": project, "slug": slug}
    if "totalTokens" in response:
        fields["totalTokens"] = response["totalTokens"]
    usage = mapping(response.get("usage"))
    if usage:
        fields["usage"] = {key: usage[key] for key in USAGE_COUNTS if key in usage}
    return fields


BUILDERS = {"spawn": spawn, "start": start, "stop": stop, "finish": finish}
TOOL_EVENTS = {"PreToolUse": "spawn", "PostToolUse": "finish"}
SUBAGENT_EVENTS = {"SubagentStart": "start", "SubagentStop": "stop"}


def classify(payload):
    """(event, agent_type, parent_agent_type); for the Agent tool the agent is the callee, the top-level
    agent_type is its caller. (None, None, None) for anything else."""
    name = payload.get("hook_event_name")
    if name in TOOL_EVENTS and payload.get("tool_name") == "Agent":
        callee = mapping(payload.get("tool_input")).get("subagent_type") \
            or mapping(payload.get("tool_response")).get("agentType")
        return TOOL_EVENTS[name], callee, payload.get("agent_type")
    if name in SUBAGENT_EVENTS:
        return SUBAGENT_EVENTS[name], payload.get("agent_type"), None
    return None, None, None


def log(payload):
    event, agent_type, parent_agent_type = classify(payload)
    if not event or not isinstance(agent_type, str) or not agent_type.startswith("argani:"):
        return
    home = argani_home.home_path()
    if not home.is_dir():
        return
    now = datetime.now(timezone.utc)
    record = {"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "event": event,
              "session_id": payload.get("session_id"), "agent_type": agent_type}
    if event in ("spawn", "finish"):
        record["parent_agent_type"] = parent_agent_type
    record.update(BUILDERS[event](payload))
    folder = home / argani_home.EVENTS_DIR
    folder.mkdir(exist_ok=True)
    with open(folder / f"{now.astimezone().strftime('%Y-%m-%d')}.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def main():
    try:
        payload = read_payload()
        if payload is not None:
            log(payload)
    except Exception as error:  # an observer must never break the session
        print(f"argani hook: log_events error: {error!r}", file=sys.stderr)


if __name__ == "__main__":
    main()
