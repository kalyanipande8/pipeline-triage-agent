"""Generate the 50-log benchmark set used by scripts/benchmark.py.

Each log is a short synthetic snippet resembling a real orchestrator (e.g.
Airflow/Dagster) task log. Most logs carry a clean signal for their labeled
failure mode; a subset are deliberately noisy (mixed signals, or vague
wording) to keep the benchmark honest rather than rigged for 100% accuracy.

Re-run this script to regenerate data/sample_logs/ and labels.csv from
scratch (it wipes the directory first).
"""

from __future__ import annotations

import csv
import random
import shutil
from pathlib import Path

random.seed(7)

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_logs"

JOB_NAMES = [
    "daily_orders_etl", "user_events_agg", "inventory_sync", "clickstream_dedupe",
    "revenue_rollup", "customer_churn_features", "warehouse_load", "ad_impressions_join",
]

# (template, baseline_manual_minutes) - manual minutes reflects a rough
# estimate of how long an on-call engineer typically takes to read the log,
# search runbooks/Slack history, and identify this failure mode by hand.
TEMPLATES: dict[str, list[str]] = {
    "out_of_memory": [
        "Task {job} failed: java.lang.OutOfMemoryError: Java heap space\nContainer killed, exit code 137 (OOMKilled)",
        "Worker process for {job} was killed: signal 9 (SIGKILL). dmesg: Out of memory: Killed process (python3)",
        "{job}: MemoryError while loading dataframe into memory (requested 18.2GB, limit 16GB)\nExceeded memory limit for pod",
        "ERROR {job}: cannot allocate memory for shuffle buffer, spark executor exited with OOM",
        "{job} task failed. Reason: Container exceeded memory limit of 8192Mi and was OOMKilled by kubelet.",
    ],
    "timeout": [
        "{job} task timed out after 3600s. Marking as failed.\nExecutionTimeout: task did not complete within SLA window",
        "TimeoutError: {job} exceeded time limit of 45 minutes, killing task",
        "{job}: read timeout while waiting for query to return (timeout=120s)",
        "Task {job} failed: deadline exceeded (context.DeadlineExceeded)",
        "{job} took longer than the configured max_runtime (2h), scheduler terminated it",
    ],
    "network_error": [
        "{job}: requests.exceptions.ConnectionError: Connection refused to host api.internal:8443",
        "{job} failed: could not resolve host 'warehouse-db.internal' - DNS resolution failed",
        "socket error in {job}: [Errno 111] Connection refused",
        "{job}: Connection reset by peer while streaming data from source",
        "network is unreachable: {job} could not reach s3.amazonaws.com",
        "{job}: unable to connect to broker after 5 attempts, giving up",
        "{job} failed with urllib3.exceptions.NewConnectionError: connection refused",
    ],
    "schema_validation_error": [
        "{job}: schema validation failed - unexpected column 'discount_pct' not in expected schema",
        "{job} failed: type mismatch on column 'user_id', expected INT64 got STRING",
        "ValidationError in {job}: missing required field 'event_timestamp' in 214 records",
        "{job}: parse error at line 4821 - malformed csv record (unescaped delimiter)",
        "{job} task failed: invalid schema, column 'order_total' not found in source table",
        "{job}: JSON decode error - malformed json record in batch 17",
        "{job} rejected 3,402 rows: type mismatch on 'created_at' (expected TIMESTAMP)",
    ],
    "permission_denied": [
        "{job} failed: 403 Forbidden - access denied to bucket 'prod-warehouse-raw'",
        "{job}: AuthenticationFailed - invalid credentials for service account pipeline-runner@prod",
        "PermissionError: {job} received permission denied writing to /data/warehouse/{job}",
        "{job} failed: 401 Unauthorized, expired token for API key used by connector",
        "{job}: access to table 'finance.transactions' denied - insufficient IAM role",
        "unauthorized: {job} could not authenticate against the metadata store",
        "{job} failed: credentials for the service account have expired, authentication failed",
    ],
    "dependency_missing": [
        "{job} failed: ModuleNotFoundError: No module named 'pyarrow'",
        "{job}: ImportError - cannot import name 'DataFrame' from partially initialized module 'pandas'",
        "{job} task crashed: package 'protobuf==3.20.1' not found in environment",
        "bash: dbt: command not found - {job} step aborted",
        "{job} failed to start: dependency 'great_expectations' missing from image",
        "{job}: version conflict between numpy==1.21 and installed scipy build",
    ],
    "upstream_data_delay": [
        "{job}: upstream table 'raw.events' not ready - partition for 2026-08-10 not found",
        "{job} waiting on upstream sensor 'orders_ingested', still not satisfied after 4 retries",
        "{job}: source table is empty for the requested date, skipping run",
        "{job} failed: no data available for partition dt=2026-08-10",
        "{job}: stale partition detected, upstream job 'raw_ingest' has not run in 26 hours",
        "{job}: partition 2026-08-10 not found in 'raw.clicks', upstream likely delayed",
    ],
}

# Manual triage minutes are drawn from a range per category (ambiguous
# categories like schema/upstream tend to take a human longer to confirm).
MANUAL_MINUTES_RANGE = {
    "out_of_memory": (8, 15),
    "timeout": (6, 12),
    "network_error": (5, 10),
    "schema_validation_error": (12, 22),
    "permission_denied": (10, 18),
    "dependency_missing": (8, 14),
    "upstream_data_delay": (10, 20),
}

# A handful of intentionally ambiguous logs that mix signals from two
# categories, to keep the benchmark from being trivially 100% accurate.
NOISY_LOGS = [
    (
        "noisy_01.log",
        "schema_validation_error",
        "revenue_rollup: task failed after retrying due to connection reset; "
        "downstream also reports type mismatch on column 'order_total' once the retry succeeded",
    ),
    (
        "noisy_02.log",
        "permission_denied",
        "warehouse_load: 403 Forbidden accessing bucket, retry also hit a read timeout "
        "before the credentials error surfaced",
    ),
    (
        "noisy_03.log",
        "network_error",
        "customer_churn_features: connection refused to feature store, "
        "logs also show a validation warning about a deprecated column that is unrelated",
    ),
    (
        "noisy_04.log",
        "out_of_memory",
        "daily_orders_etl: task killed, exit code 137, occurred right after a 90-minute "
        "run that was already flirting with the statement timeout",
    ),
    (
        "noisy_05.log",
        "dependency_missing",
        "ad_impressions_join: build step failed - package not found in image, "
        "preceding step also logged a 401 from the internal package index",
    ),
    (
        "noisy_06.log",
        "upstream_data_delay",
        "inventory_sync: run skipped, upstream partition not found; the same task also "
        "logged a stale credentials warning from an earlier retry",
    ),
    (
        "noisy_07.log",
        "timeout",
        "user_events_agg: task still running past the SLA window, meanwhile a downstream "
        "consumer reported a missing column on the last successful output",
    ),
]


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    rows = []
    idx = 1

    for label, templates in TEMPLATES.items():
        lo, hi = MANUAL_MINUTES_RANGE[label]
        for template in templates:
            job = random.choice(JOB_NAMES)
            text = template.format(job=job)
            fname = f"{idx:02d}_{label}.log"
            (OUT_DIR / fname).write_text(text + "\n")
            rows.append(
                {
                    "filename": fname,
                    "label": label,
                    "baseline_manual_minutes": random.randint(lo, hi),
                }
            )
            idx += 1

    for fname, label, text in NOISY_LOGS:
        lo, hi = MANUAL_MINUTES_RANGE[label]
        (OUT_DIR / fname).write_text(text + "\n")
        rows.append(
            {
                "filename": fname,
                "label": label,
                "baseline_manual_minutes": random.randint(lo + 5, hi + 8),
            }
        )

    with (OUT_DIR / "labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "label", "baseline_manual_minutes"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} logs + labels.csv to {OUT_DIR}")


if __name__ == "__main__":
    main()
