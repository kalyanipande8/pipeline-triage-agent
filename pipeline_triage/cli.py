"""Command-line entry point.

The agent only ever *proposes* an action. Nothing in ``ACTIONS`` runs
automatically — a human must type ``y`` at the confirmation prompt before a
decision is recorded as approved. Every triage (approved or declined) is
appended to an append-only decision log for audit purposes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .actions import get_action
from .classifier import classify
from .llm_agent import classify_with_llm, llm_available

DECISION_LOG = Path("decision_log.jsonl")


def _log_decision(record: dict) -> None:
    with DECISION_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


def triage_one(log_path: Path, auto_yes: bool, use_llm: bool) -> dict:
    log_text = log_path.read_text()
    result = classify_with_llm(log_text) if use_llm else classify(log_text)
    action = get_action(result.label)

    print(f"\n=== {log_path.name} ===")
    print(f"Predicted failure mode : {result.label}  (confidence {result.confidence:.2f})")
    print(f"Proposed action        : {action.summary}  [risk: {action.risk}]")
    print(f"Detail                 : {action.detail}")

    approved = auto_yes
    if not auto_yes:
        reply = input("Approve this action? [y/N] ").strip().lower()
        approved = reply == "y"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "log_file": str(log_path),
        "predicted_label": result.label,
        "confidence": result.confidence,
        "proposed_action": action.summary,
        "risk": action.risk,
        "approved": approved,
    }
    _log_decision(record)
    print("Approved - action recorded." if approved else "Declined - no action taken.")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pipeline-triage",
        description="Agent-assisted pipeline failure triage with human sign-off.",
    )
    parser.add_argument("path", type=Path, help="A log file, or a directory of log files")
    parser.add_argument(
        "--yes", action="store_true", help="Auto-approve proposed actions (skip the confirmation prompt)"
    )
    parser.add_argument(
        "--llm", action="store_true", help="Use the Claude-backed classifier instead of the rule-based one"
    )
    args = parser.parse_args(argv)

    if args.llm and not llm_available():
        print(
            "Warning: --llm requested but ANTHROPIC_API_KEY is not set or the "
            "anthropic package is not installed. Falling back to the rule-based classifier.",
            file=sys.stderr,
        )

    if args.path.is_dir():
        log_files = sorted(args.path.glob("*.log")) + sorted(args.path.glob("*.txt"))
    else:
        log_files = [args.path]

    if not log_files:
        print(f"No log files found at {args.path}", file=sys.stderr)
        return 1

    for log_file in log_files:
        triage_one(log_file, auto_yes=args.yes, use_llm=args.llm)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
