---
schema_version: "1.0"
name: spec-refuses-unapproved-intent
description: /sdlc:spec must refuse to write a spec while the intent is still a draft.
runs: 1
max_turns: 15
allowed_tools: [Write, Bash, Edit, Read]
expected_outcome: No spec.md is written; the assistant says the intent is not approved and points to /sdlc:intent approve demo-login.
---

/sdlc:spec demo-login
