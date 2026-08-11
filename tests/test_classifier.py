import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline_triage.classifier import FAILURE_MODES, classify


def test_out_of_memory():
    log = "Task etl_job failed: java.lang.OutOfMemoryError: Java heap space"
    result = classify(log)
    assert result.label == "out_of_memory"
    assert result.confidence > 0


def test_network_error():
    log = "requests.exceptions.ConnectionError: Connection refused to host api.internal"
    assert classify(log).label == "network_error"


def test_schema_validation_error():
    log = "schema validation failed - unexpected column 'discount_pct' not in expected schema"
    assert classify(log).label == "schema_validation_error"


def test_permission_denied():
    log = "403 Forbidden - access denied to bucket 'prod-warehouse-raw'"
    assert classify(log).label == "permission_denied"


def test_dependency_missing():
    log = "ModuleNotFoundError: No module named 'pyarrow'"
    assert classify(log).label == "dependency_missing"


def test_upstream_data_delay():
    log = "upstream table 'raw.events' not ready - partition for 2026-08-10 not found"
    assert classify(log).label == "upstream_data_delay"


def test_timeout():
    log = "TimeoutError: job exceeded time limit of 45 minutes, killing task"
    assert classify(log).label == "timeout"


def test_unknown_when_no_signal_matches():
    result = classify("Job completed successfully, all rows loaded.")
    assert result.label == "unknown"
    assert result.confidence == 0.0


def test_all_seven_failure_modes_defined():
    assert len(FAILURE_MODES) == 7
