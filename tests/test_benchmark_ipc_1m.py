import importlib.util
from pathlib import Path

import pytest


BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "benchmark_ipc_1m.py"
)

SPEC = importlib.util.spec_from_file_location(
    "benchmark_ipc_1m",
    BENCHMARK_PATH,
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


@pytest.fixture
def valid_record():
    return {
        "sequence": 4,
        "timestamp_ns": 1000,
        "price_ticks": 5,
        "quantity": 1,
        "side": 1,
    }


def test_valid_record_has_no_payload_errors(valid_record):
    errors = benchmark.validate_record(valid_record, 4, 900, 1100)

    assert errors == {
        "sequence": False,
        "timestamp": False,
        "price_ticks": False,
        "quantity": False,
        "side": False,
    }


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("sequence", 99),
        ("price_ticks", 99),
        ("quantity", 2),
        ("side", 2),
    ],
)
def test_payload_fields_are_validated_independently(
    valid_record, field, bad_value
):
    valid_record[field] = bad_value
    errors = benchmark.validate_record(valid_record, 4, 900, 1100)

    assert errors[field] is True
    assert sum(errors.values()) == 1


@pytest.mark.parametrize(
    ("timestamp", "previous", "now"),
    [
        (-1, None, 1100),
        (1200, None, 1100),
        (899, 900, 1100),
        ("1000", None, 1100),
    ],
)
def test_invalid_timestamp_is_detected(
    valid_record, timestamp, previous, now
):
    valid_record["timestamp_ns"] = timestamp
    errors = benchmark.validate_record(valid_record, 4, previous, now)

    assert errors["timestamp"] is True
    assert sum(errors.values()) == 1


def test_timestamp_must_not_decrease(valid_record):
    valid_record["timestamp_ns"] = 999
    errors = benchmark.validate_record(valid_record, 4, 1000, 1100)

    assert errors["timestamp"] is True

@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("sequence", "4"),
        ("price_ticks", 5.5),
        ("quantity", True),
        ("side", "1"),
    ],
)
def test_invalid_field_types_are_rejected(valid_record, field, bad_value):
    valid_record[field] = bad_value
    errors = benchmark.validate_record(valid_record, 4, 900, 1100)

    assert errors[field] is True
    assert sum(errors.values()) == 1


def test_consumer_counts_invalid_payload_and_benchmark_fails(monkeypatch):
    record = {
        "sequence": 99,
        "timestamp_ns": 1,
        "price_ticks": 1,
        "quantity": 1,
        "side": 1,
    }

    class FakeRing:
        def __init__(self, *args, **kwargs):
            self.records = [record]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            if self.records:
                return self.records.pop(0)
            return None

    class FakeResults:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    monkeypatch.setattr("ipc.ring_buffer.RingBuffer", FakeRing)

    results = FakeResults()
    benchmark.consumer("unused", 2, 1, results)

    assert len(results.items) == 1

    who, status, stats = results.items[0]

    assert who == "consumer"
    assert status == "ok"
    assert stats["received"] == 1
    assert stats["payload_errors"]["sequence"] == 1
    assert stats["out_of_order"] == 1
    assert stats["latency_samples"] == 1

    assert benchmark.benchmark_result(1, 1, stats) == "FAIL"
