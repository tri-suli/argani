import json
from datetime import datetime

import argani_home
from hook_helpers import HOOKS_DIR, run_hook

SESSION = "session-1"


def prompt_for(hub, slug="login"):
    return f"Review it.\nSlug folder: {hub}/projects/demo/tasks/{slug}\nRound: 1"


def spawn_payload(prompt, subagent_type="argani:builder"):
    return {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": SESSION, "cwd": "/work",
            "tool_use_id": "toolu_1",
            "tool_input": {"description": "d", "prompt": prompt, "subagent_type": subagent_type,
                           "model": "sonnet"}}


def finish_payload(prompt):
    return {"hook_event_name": "PostToolUse", "tool_name": "Agent", "session_id": SESSION,
            "tool_use_id": "toolu_1", "duration_ms": 1234,
            "tool_input": {"prompt": prompt, "subagent_type": "argani:builder"},
            "tool_response": {"status": "completed", "agentId": "agent-9", "agentType": "argani:builder",
                              "totalTokens": 77,
                              "usage": {"input_tokens": 1, "output_tokens": 2, "cache_creation_input_tokens": 3,
                                        "cache_read_input_tokens": 4, "iterations": [], "service_tier": "x"}}}


START = {"hook_event_name": "SubagentStart", "session_id": SESSION, "agent_id": "agent-9",
         "agent_type": "argani:builder"}
STOP = {"hook_event_name": "SubagentStop", "session_id": SESSION, "agent_id": "agent-9",
        "agent_type": "argani:builder", "agent_transcript_path": "/t.jsonl", "last_assistant_message": "done"}


def logged(hub):
    files = list((hub / "events").glob("*.jsonl"))
    return [json.loads(line) for file in files for line in file.read_text().splitlines()]


def test_without_a_home_nothing_is_written(tmp_path):
    assert run_hook("log_events.py", START) is None
    assert not (tmp_path / "argani-home").exists()


def test_spawn_line(hub, register_project):
    register_project("demo")
    run_hook("log_events.py", spawn_payload(prompt_for(hub)))
    (line,) = logged(hub)
    assert line["event"] == "spawn" and line["agent_type"] == "argani:builder"
    assert line["session_id"] == SESSION and line["ts"].endswith("Z")
    assert (line["tool_use_id"], line["model"], line["cwd"]) == ("toolu_1", "sonnet", "/work")
    assert (line["project"], line["slug"]) == ("demo", "login")


def test_spec_writer_intent_path_gives_project_and_slug(hub, register_project):
    register_project("demo")
    prompt = f"Intent: {hub}/projects/demo/tasks/login/intent.md"
    run_hook("log_events.py", spawn_payload(prompt, "argani:spec-writer"))
    assert (logged(hub)[0]["project"], logged(hub)[0]["slug"]) == ("demo", "login")


def test_start_line(hub):
    run_hook("log_events.py", START)
    (line,) = logged(hub)
    assert (line["event"], line["agent_id"], line["agent_type"]) == ("start", "agent-9", "argani:builder")


def test_stop_line_truncates_the_last_message(hub):
    run_hook("log_events.py", {**STOP, "last_assistant_message": "x" * 800})
    (line,) = logged(hub)
    assert line["event"] == "stop" and line["agent_transcript_path"] == "/t.jsonl"
    assert line["last_assistant_message"] == "x" * 500


def test_finish_line(hub, register_project):
    register_project("demo")
    run_hook("log_events.py", finish_payload(prompt_for(hub)))
    (line,) = logged(hub)
    assert line["event"] == "finish" and line["agent_type"] == "argani:builder"
    assert (line["tool_use_id"], line["agent_id"], line["status"]) == ("toolu_1", "agent-9", "completed")
    assert (line["duration_ms"], line["totalTokens"]) == (1234, 77)
    assert line["usage"] == {"input_tokens": 1, "output_tokens": 2, "cache_creation_input_tokens": 3,
                             "cache_read_input_tokens": 4}
    assert (line["project"], line["slug"]) == ("demo", "login")


def test_non_argani_agent_is_not_logged(hub):
    run_hook("log_events.py", spawn_payload("x", "general-purpose"))
    run_hook("log_events.py", {**START, "agent_type": "Explore"})
    assert logged(hub) == []


def test_prompt_without_a_job_path_gives_null_project_and_slug(hub):
    run_hook("log_events.py", spawn_payload("no path here"))
    (line,) = logged(hub)
    assert (line["project"], line["slug"]) == (None, None)


def test_broken_payload_exits_0_and_writes_nothing(hub):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, str(HOOKS_DIR / "log_events.py")], input="not json",
                            capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == ""
    assert not (hub / "events").exists()


def test_file_is_named_after_today(hub):
    run_hook("log_events.py", START)
    assert [file.name for file in (hub / "events").iterdir()] == [datetime.now().strftime("%Y-%m-%d") + ".jsonl"]


def test_hooks_json_registers_the_four_events():
    hooks = json.loads((HOOKS_DIR / "hooks.json").read_text())["hooks"]
    expected = {"PreToolUse": "Agent", "PostToolUse": "Agent",
                "SubagentStart": "^argani:", "SubagentStop": "^argani:"}
    for event, matcher in expected.items():
        commands = [hook["command"] for entry in hooks[event] if entry["matcher"] == matcher
                    for hook in entry["hooks"]]
        assert any(command.endswith("hooks/log_events.py\"") for command in commands), event


def test_report_has_the_events_folder(tmp_path):
    assert argani_home.report(tmp_path)["events"] == str(tmp_path / "events")


def test_spawn_logs_the_callee_and_the_caller(hub):
    run_hook("log_events.py", {**spawn_payload("x"), "agent_type": "general-purpose"})
    (line,) = logged(hub)
    assert (line["agent_type"], line["parent_agent_type"]) == ("argani:builder", "general-purpose")


def test_main_session_spawn_has_a_null_parent(hub):
    run_hook("log_events.py", spawn_payload("x"))
    assert logged(hub)[0]["parent_agent_type"] is None


def test_quoted_intent_title_before_the_slug_folder_still_resolves(hub, register_project):
    register_project("demo")
    run_hook("log_events.py", spawn_payload(f"# Intent: Demo\nSlug folder: {hub}/projects/demo/tasks/login"))
    assert (logged(hub)[0]["project"], logged(hub)[0]["slug"]) == ("demo", "login")


def test_backticked_path_resolves(hub, register_project):
    register_project("demo")
    run_hook("log_events.py", spawn_payload(f"Slug folder: `{hub}/projects/demo/tasks/login`"))
    assert (logged(hub)[0]["project"], logged(hub)[0]["slug"]) == ("demo", "login")


def test_bad_field_types_are_coerced_not_dropped(hub):
    run_hook("log_events.py", {**STOP, "tool_input": "oops", "last_assistant_message": 5})
    (line,) = logged(hub)
    assert line["event"] == "stop" and line["last_assistant_message"] == ""
    run_hook("log_events.py", {**spawn_payload("x"), "tool_input": {"subagent_type": "argani:builder", "prompt": 3}})
    assert len(logged(hub)) == 2


def test_invalid_home_prints_nothing_for_a_non_argani_agent(monkeypatch):
    monkeypatch.setenv("ARGANI_HOME", "relative/path")
    assert run_hook("log_events.py", {**START, "agent_type": "Explore"}) is None
