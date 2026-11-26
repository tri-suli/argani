import pytest

import board_columns


@pytest.mark.parametrize("stage,expected", [
    ("needs-intake", "Intake"), ("needs-intent-approval", "Intake"),
    ("needs-spec", "Spec"), ("needs-spec-approval", "Spec"),
    ("needs-build", "Build"), ("needs-rework", "Build"),
    ("needs-review", "Review"),
    ("needs-decision", "Approve"), ("needs-mr", "Approve"), ("needs-merge", "Approve"),
    ("needs-human", "Needs human"), ("error", "Needs human"), ("surprise", "Needs human"),
    ("done", "Done"), ("cancelled", "Done"),
])
def test_stage_maps_to_column(stage, expected):
    assert board_columns.column(stage, False) == expected


def test_columns_order():
    assert board_columns.COLUMNS == ("Intake", "Spec", "Build", "Review", "Approve", "Needs human", "Done")


@pytest.mark.parametrize("stage", ["needs-intake", "needs-build", "needs-merge", "error", "surprise"])
def test_answered_moves_to_approve(stage):
    assert board_columns.column(stage, True) == "Approve"


@pytest.mark.parametrize("stage,expected", [("done", "Done"), ("cancelled", "Done"), ("needs-human", "Needs human")])
def test_answered_keeps_terminal_and_needs_human(stage, expected):
    assert board_columns.column(stage, True) == expected
