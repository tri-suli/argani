---
name: board
description: Show the argani board, the tasks of this directory's project (or of every project with --all) by column - Intake, Spec, Build, Review, Approve, Needs human, Done. Read only. Slash form /argani:board [--all].
argument-hint: "[--all]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read
---

# /argani:board

Columns and how a task lands in one: the "Board" section of `${CLAUDE_PLUGIN_ROOT}/docs/argani.md`.
This skill only reads. It writes nothing and never runs the factory.

## Steps

1. Run exactly one of two commands, never anything the user typed: with no arguments,
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/board.py`; with the single argument `--all`,
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/board.py --all`. Any other argument: show the usage
   `/argani:board [--all]` and stop.
2. If it exits 1 with "This directory is not registered in the argani home ...", show the message
   and suggest `/argani:init` in this directory, or `/argani:board --all` for every project.
   Stop. On any other non-zero exit, show its output and stop; fix nothing.
3. If it exits 0, print the markdown as is: do not reorder, summarise or drop tasks. Show any
   warning it printed on stderr (a skipped project). Then add one line with the number of tasks per
   non-empty column.
4. Only when the human asks how to move a task, name the command for its column and leave the
   human to run it: Intake, Spec, Build, Review and Approve are all advanced by
   `/argani:factory <slug>` (the factory writes and approves intent and spec itself; the manual loop
   uses `/argani:intent approve <slug>` and `/argani:spec approve <slug>`); Done needs no command; Needs human shows the question of the task
   (the `question:` line), answered with `/argani:factory answer <slug> <answer>`.
