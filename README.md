# Agent-Assisted Pipeline Triage Tool

Classifies data pipeline run-log failures into one of 7 known failure modes
and proposes a remediation action — but never takes that action without an
explicit human sign-off.

## Why

On-call engineers spend a lot of triage time just figuring out *which kind*
of failure they're looking at before they can act. This tool automates that
first step (classification + suggested next action) while keeping a human
in the loop for anything that actually touches infrastructure or data.

## The 7 failure modes

| Failure mode               | Example signal                                  |
|-----------------------------|--------------------------------------------------|
| `out_of_memory`             | `OOMKilled`, `MemoryError`, exit code 137         |
| `timeout`                   | `DeadlineExceeded`, task exceeded SLA window      |
| `network_error`             | `Connection refused`, DNS resolution failed       |
| `schema_validation_error`   | unexpected column, type mismatch, parse error     |
| `permission_denied`         | `403 Forbidden`, expired token, invalid creds     |
| `dependency_missing`        | `ModuleNotFoundError`, version conflict           |
| `upstream_data_delay`       | upstream partition not found, stale data          |

See [`pipeline_triage/classifier.py`](pipeline_triage/classifier.py) for the
full signal list and [`pipeline_triage/actions.py`](pipeline_triage/actions.py)
for the recommended action + risk level per category.

## How it works

1. **Classify** — a rule-based signal classifier runs offline by default
   ([`classifier.py`](pipeline_triage/classifier.py)); pass `--llm` to use a
   Claude-backed classifier instead (falls back automatically if
   `ANTHROPIC_API_KEY` isn't set — see [`llm_agent.py`](pipeline_triage/llm_agent.py)).
2. **Propose** — the matching category maps to a recommended action and risk
   level ([`actions.py`](pipeline_triage/actions.py)).
3. **Human sign-off** — the CLI prints the proposed action and prompts for
   explicit approval before recording it as taken. Nothing is auto-executed;
   every decision (approved or declined) is appended to `decision_log.jsonl`.

## Usage

```bash
pip install -r requirements.txt   # only needed for --llm mode

# Triage a single log, with a confirmation prompt
python3 -m pipeline_triage.cli data/sample_logs/01_out_of_memory.log

# Triage a whole directory of logs
python3 -m pipeline_triage.cli data/sample_logs/

# Use the Claude-backed classifier (requires ANTHROPIC_API_KEY)
python3 -m pipeline_triage.cli data/sample_logs/ --llm
```

## Benchmark

`data/sample_logs/` contains 50 synthetic-but-realistic log snippets
(regenerate with `scripts/generate_sample_logs.py`), each labeled with its
true failure mode and an estimated manual-diagnosis time. Some are
intentionally noisy (mixed signals across categories) so the benchmark isn't
trivially 100%.

```bash
python3 scripts/benchmark.py
```

Latest run on this repo's `main`:

```
Overall accuracy: 42/50 = 84.0%

category                  correct/total   accuracy
out_of_memory             5/6                 83%
timeout                   4/6                 67%
network_error             8/8                100%
schema_validation_error   7/8                 88%
permission_denied         6/8                 75%
dependency_missing        6/7                 86%
upstream_data_delay       6/7                 86%

Baseline (manual) diagnosis time for these 50 failures: 653 min (10.9h)
Agent classification wall time for the same 50 failures: 0.00s
```

The manual-diagnosis-time baseline is an illustrative estimate per category
(logged in `labels.csv`), not measured production data — the point of the
benchmark is the classification-accuracy number and the relative order-of-
magnitude time gap, not a precise SLA claim.

## Project layout

```
pipeline_triage/
  classifier.py   # rule-based (offline) failure classifier
  llm_agent.py     # optional Claude-backed classifier, same taxonomy
  actions.py        # recommended action + risk per failure mode
  cli.py             # human-in-the-loop CLI entry point
scripts/
  generate_sample_logs.py   # regenerates data/sample_logs/
  benchmark.py                # scores the classifier against labels.csv
tests/
  test_classifier.py
  test_actions.py
```

## Running tests

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest tests/ -q
```
