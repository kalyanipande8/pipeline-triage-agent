import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline_triage.actions import ACTIONS, get_action
from pipeline_triage.classifier import FAILURE_MODES


def test_every_failure_mode_has_an_action():
    for mode in FAILURE_MODES:
        assert mode in ACTIONS


def test_unknown_falls_back_to_escalation():
    action = get_action("something_not_in_taxonomy")
    assert action is ACTIONS["unknown"]


def test_actions_have_required_fields():
    for action in ACTIONS.values():
        assert action.summary
        assert action.risk in {"low", "medium", "high"}
        assert action.detail
