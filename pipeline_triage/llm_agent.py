"""Optional LLM-backed classifier.

If ``ANTHROPIC_API_KEY`` is set and the ``anthropic`` package is installed,
``classify_with_llm`` asks Claude to pick one of the 7 failure modes and
give a short rationale. Otherwise it transparently falls back to the
rule-based classifier in ``classifier.py`` so the tool works offline.
"""

from __future__ import annotations

import json
import os

from .classifier import FAILURE_MODES, Classification, classify

SYSTEM_PROMPT = f"""You are a pipeline failure triage assistant. You will be shown a \
snippet of a data pipeline's run log. Classify the failure into exactly one of \
these categories:

{chr(10).join(f"- {mode}" for mode in FAILURE_MODES)}

Respond with ONLY a JSON object of the form:
{{"label": "<one of the categories above>", "confidence": <0-1 float>, "rationale": "<one sentence>"}}

If nothing in the log matches any category, use "unknown" as the label."""


def llm_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def classify_with_llm(log_text: str, model: str = "claude-sonnet-5") -> Classification:
    """Classify using Claude if configured, else fall back to rule-based."""
    if not llm_available():
        return classify(log_text)

    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": log_text}],
    )
    raw = response.content[0].text.strip()

    try:
        parsed = json.loads(raw)
        label = parsed.get("label", "unknown")
        confidence = float(parsed.get("confidence", 0.5))
        if label not in FAILURE_MODES and label != "unknown":
            label = "unknown"
        return Classification(label=label, confidence=confidence, matched_signals=[parsed.get("rationale", "")])
    except (json.JSONDecodeError, ValueError, KeyError):
        # Model didn't return clean JSON - fall back rather than guess.
        return classify(log_text)
