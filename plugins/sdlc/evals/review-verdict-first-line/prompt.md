---
schema_version: "1.0"
name: review-verdict-first-line
description: /sdlc:review spawns the code reviewer, which writes a file whose first line is the verdict and which ends with the closing line.
runs: 1
max_turns: 30
allowed_tools: [Write, Bash, Edit, Read, Agent]
expected_outcome: review-code.md exists, starts with PASS or CHANGES, ends with the closing line, and flags the bug in calc.py with CHANGES.
---

/sdlc:review demo-login
