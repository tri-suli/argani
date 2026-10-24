---
type: llm
focus:
  source: file
  path: sdlc/demo-login/review/round-1/review-code.md
---
The repository's calc.py implements add(a, b) as `a - b`, which is wrong. You are given the review file. PASS only if the verdict on line 1 of the review is CHANGES and at least one finding names calc.py as the location of the bug. Otherwise FAIL.
