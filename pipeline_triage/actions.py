"""Recommended remediation actions per failure mode.

No action defined here ever executes automatically. ``cli.py`` always
prompts a human for explicit sign-off before an action is recorded as
"taken" — this module only describes what *would* happen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Action:
    summary: str
    risk: str  # "low", "medium", "high"
    detail: str


ACTIONS: dict[str, Action] = {
    "out_of_memory": Action(
        summary="Bump executor memory and retry the job",
        risk="medium",
        detail=(
            "Increase memory allocation for the failing task (e.g. one tier up) "
            "and resubmit. If it recurs, check for a recent data volume spike or "
            "an unbounded in-memory join."
        ),
    ),
    "timeout": Action(
        summary="Increase timeout threshold and retry",
        risk="low",
        detail=(
            "Retry with a longer timeout window. If the job is trending slower "
            "over time, flag for a performance review rather than repeatedly "
            "extending the timeout."
        ),
    ),
    "network_error": Action(
        summary="Retry with backoff; check downstream service health",
        risk="low",
        detail=(
            "Transient network failures usually clear on retry. If retries keep "
            "failing, check the status of the remote endpoint/DNS before "
            "escalating to on-call."
        ),
    ),
    "schema_validation_error": Action(
        summary="Quarantine the batch and notify the upstream data owner",
        risk="high",
        detail=(
            "Do not force the batch through. Move it to a quarantine location, "
            "diff the observed schema against the expected contract, and file a "
            "ticket with the upstream team."
        ),
    ),
    "permission_denied": Action(
        summary="Rotate/verify credentials before retrying",
        risk="high",
        detail=(
            "Check for an expired token or revoked service-account permission. "
            "Rotate credentials via the secrets manager, then retry — do not "
            "retry blindly, as repeated auth failures can trigger lockouts."
        ),
    ),
    "dependency_missing": Action(
        summary="Pin/install the missing dependency and rebuild the environment",
        risk="medium",
        detail=(
            "Likely an environment drift issue (unpinned version, stale image). "
            "Rebuild the execution environment from the lockfile and retry."
        ),
    ),
    "upstream_data_delay": Action(
        summary="Reschedule downstream of the upstream SLA, do not force-run",
        risk="medium",
        detail=(
            "The pipeline ran ahead of its data dependency. Reschedule for after "
            "the upstream SLA, or add an explicit sensor/dependency check instead "
            "of a fixed-time trigger."
        ),
    ),
    "unknown": Action(
        summary="Escalate to on-call for manual triage",
        risk="high",
        detail=(
            "No known failure signature matched. This should go to a human "
            "immediately rather than being auto-retried."
        ),
    ),
}


def get_action(label: str) -> Action:
    return ACTIONS.get(label, ACTIONS["unknown"])
