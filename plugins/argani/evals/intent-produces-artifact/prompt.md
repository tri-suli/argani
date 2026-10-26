---
schema_version: "1.0"
name: intent-produces-artifact
description: /argani:intent turns a short description into a valid draft intent.md.
runs: 1
max_turns: 25
allowed_tools: [Write, Bash, Edit, Read]
expected_outcome: argani/demo-login/intent.md exists, is a draft, and every acceptance criterion carries a verify tail.
---

/argani:intent Add rate limiting to the login endpoint. Today anyone can try unlimited passwords, which exposes users to credential stuffing. We want at most 5 failed attempts per account per 15 minutes, after which the endpoint answers with HTTP 429. It must not lock out legitimate users for longer than 15 minutes.

Use the slug demo-login and do not ask questions; make reasonable assumptions and write the file.
