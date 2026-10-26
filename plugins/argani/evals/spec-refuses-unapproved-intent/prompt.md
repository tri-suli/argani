---
schema_version: "1.0"
name: spec-refuses-unapproved-intent
description: /argani:spec must refuse to write a spec while the intent is still a draft.
runs: 1
max_turns: 15
allowed_tools: [Write, Bash, Edit, Read]
expected_outcome: No spec.md is written; the assistant says the intent is not approved and points to /argani:intent approve demo-login.
---

/argani:spec demo-login
