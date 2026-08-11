"""Rule-based failure classifier.

This is the offline, deterministic fallback used when no LLM API key is
configured (and the classifier the benchmark script scores against). The
LLM-backed classifier in ``llm_agent.py`` wraps this module's category
definitions in its prompt so both paths agree on the taxonomy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# The 7 failure modes the agent recognizes.
FAILURE_MODES = [
    "out_of_memory",
    "timeout",
    "network_error",
    "schema_validation_error",
    "permission_denied",
    "dependency_missing",
    "upstream_data_delay",
]

# Ordered (priority) keyword/regex signals per failure mode. Order matters
# for tie-breaking: earlier categories win when signal counts are equal.
_SIGNALS: dict[str, list[str]] = {
    "out_of_memory": [
        r"out of memory",
        r"oom\b",
        r"oomkilled",
        r"memoryerror",
        r"killed.*signal 9",
        r"exceeded memory limit",
        r"cannot allocate memory",
    ],
    "timeout": [
        r"timed? ?out",
        r"deadline exceeded",
        r"exceeded.*time limit",
        r"task took longer than",
        r"read timeout",
        r"connection timeout",
    ],
    "network_error": [
        r"connection refused",
        r"connection reset",
        r"dns resolution failed",
        r"could not resolve host",
        r"network is unreachable",
        r"socket error",
        r"unable to connect",
    ],
    "schema_validation_error": [
        r"schema validation failed",
        r"unexpected column",
        r"type mismatch",
        r"missing required field",
        r"invalid schema",
        r"column .* not found",
        r"parse error",
        r"malformed (json|csv|record)",
    ],
    "permission_denied": [
        r"permission denied",
        r"access denied",
        r"unauthorized",
        r"forbidden",
        r"invalid credentials",
        r"authentication failed",
        r"expired token",
    ],
    "dependency_missing": [
        r"modulenotfounderror",
        r"no module named",
        r"package .* not found",
        r"dependency .* missing",
        r"version conflict",
        r"import ?error",
        r"command not found",
    ],
    "upstream_data_delay": [
        r"upstream (table|dataset|partition) not (ready|available)",
        r"waiting on upstream",
        r"partition .* not found",
        r"no data (available|found) for",
        r"source table is empty",
        r"stale (data|partition)",
    ],
}

_COMPILED = {
    mode: [re.compile(p, re.IGNORECASE) for p in patterns]
    for mode, patterns in _SIGNALS.items()
}


@dataclass
class Classification:
    label: str
    confidence: float
    matched_signals: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)


def classify(log_text: str) -> Classification:
    """Classify a log's failure mode using keyword/regex signal counting.

    Each category's patterns are matched against the log text; the category
    with the most matches wins (ties broken by taxonomy order). Confidence
    is the winning category's share of total signal hits, so an unambiguous
    log with 3 matching signals and 0 elsewhere reports confidence 1.0,
    while a log with mixed signals reports something lower.
    """
    scores: dict[str, int] = {mode: 0 for mode in FAILURE_MODES}
    matched: list[str] = []

    for mode, patterns in _COMPILED.items():
        for pattern in patterns:
            if pattern.search(log_text):
                scores[mode] += 1
                matched.append(f"{mode}:{pattern.pattern}")

    total_hits = sum(scores.values())
    if total_hits == 0:
        return Classification(label="unknown", confidence=0.0, matched_signals=[], scores=scores)

    best_label = max(FAILURE_MODES, key=lambda m: scores[m])
    confidence = scores[best_label] / total_hits
    return Classification(
        label=best_label,
        confidence=round(confidence, 3),
        matched_signals=matched,
        scores=scores,
    )
