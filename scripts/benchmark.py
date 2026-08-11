"""Benchmark the classifier against the 50 labeled logs in data/sample_logs.

Reports per-class and overall accuracy, and compares the agent's
(near-instant) classification time against the recorded baseline manual
diagnosis time for each log, as a proxy for the "diagnosis time" reduction
this tool targets.

Usage:
    python3 scripts/benchmark.py [--llm]
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline_triage.classifier import FAILURE_MODES, classify
from pipeline_triage.llm_agent import classify_with_llm, llm_available

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"


def load_labels() -> list[dict]:
    with (DATA_DIR / "labels.csv").open() as f:
        return list(csv.DictReader(f))


def run(use_llm: bool) -> None:
    rows = load_labels()
    per_class_total: dict[str, int] = defaultdict(int)
    per_class_correct: dict[str, int] = defaultdict(int)
    correct = 0
    total_manual_minutes = 0.0
    start = time.perf_counter()

    for row in rows:
        log_text = (DATA_DIR / row["filename"]).read_text()
        result = classify_with_llm(log_text) if use_llm else classify(log_text)
        true_label = row["label"]
        per_class_total[true_label] += 1
        total_manual_minutes += float(row["baseline_manual_minutes"])
        if result.label == true_label:
            correct += 1
            per_class_correct[true_label] += 1

    elapsed = time.perf_counter() - start
    n = len(rows)
    accuracy = correct / n

    print(f"Mode: {'LLM (Claude)' if use_llm else 'rule-based (offline)'}")
    print(f"Logs evaluated: {n}")
    print(f"Overall accuracy: {correct}/{n} = {accuracy:.1%}\n")

    print(f"{'category':<26}{'correct/total':<16}{'accuracy':>8}")
    for mode in FAILURE_MODES:
        t = per_class_total.get(mode, 0)
        c = per_class_correct.get(mode, 0)
        if t == 0:
            continue
        print(f"{mode:<26}{f'{c}/{t}':<16}{c / t:>7.0%}")

    agent_minutes = elapsed / 60
    baseline_hours = total_manual_minutes / 60
    print(f"\nBaseline (manual) diagnosis time for these {n} failures: {total_manual_minutes:.0f} min ({baseline_hours:.1f}h)")
    print(f"Agent classification wall time for the same {n} failures: {elapsed:.2f}s")
    print(
        "Note: the agent still requires a human sign-off step per log before any "
        "action is taken; the comparison above reflects diagnosis (classification), "
        "not the full remediation loop."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="Benchmark the Claude-backed classifier instead")
    args = parser.parse_args()

    if args.llm and not llm_available():
        print("ANTHROPIC_API_KEY not set (or anthropic not installed) - falling back to rule-based.", file=sys.stderr)

    run(use_llm=args.llm)


if __name__ == "__main__":
    main()
