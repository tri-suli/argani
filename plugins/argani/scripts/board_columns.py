#!/usr/bin/env python3
"""The one mapping from a task stage (factory_state.py) to a board column.

column(stage, answered) is the only place that knows which column a stage belongs to; the board
and the task history both use it. A human answer that is not acted on yet puts the task in Approve.
"""

INTAKE = "Intake"
SPEC = "Spec"
BUILD = "Build"
REVIEW = "Review"
APPROVE = "Approve"
NEEDS_HUMAN = "Needs human"
DONE = "Done"
COLUMNS = (INTAKE, SPEC, BUILD, REVIEW, APPROVE, NEEDS_HUMAN, DONE)

STAGE_COLUMNS = {
    "needs-intake": INTAKE, "needs-intent-approval": INTAKE,
    "needs-spec": SPEC, "needs-spec-approval": SPEC,
    "needs-build": BUILD, "needs-rework": BUILD,
    "needs-review": REVIEW,
    "needs-decision": APPROVE, "needs-mr": APPROVE, "needs-merge": APPROVE,
    "needs-human": NEEDS_HUMAN, "error": NEEDS_HUMAN,
    "done": DONE, "cancelled": DONE,
}
# an answer does not move these: finished tasks stay Done, a task waiting on a human stays there
ANSWER_KEEPS_COLUMN = ("done", "cancelled", "needs-human")


def column(stage, answered):
    if answered and stage not in ANSWER_KEEPS_COLUMN:
        return APPROVE
    return STAGE_COLUMNS.get(stage, NEEDS_HUMAN)
