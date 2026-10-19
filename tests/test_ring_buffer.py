import multiprocessing
import threading
import time


def _ring_buffer_producer(path, count, results):
    try:
        with RingBuffer(path, capacity=8) as ring:
            deadline = time.monotonic() + 15

            for i in range(count):
                while not ring.write(
                    timestamp_ns=i + 100,
                    price_ticks=i + 200,
                    quantity=1,
                    side=1,
                ):
                    if time.monotonic() >= deadline:
                        results.put(("timeout", i))
                        return
                    time.sleep(0.001)

        results.put(("ok", count))
    except Exception as exc:
        results.put(("error", repr(exc)))


def _ring_buffer_consumer(path, count, results):
    try:
        with RingBuffer(path, capacity=8) as ring:
            records = []
            deadline = time.monotonic() + 15

            while len(records) < count:
                record = ring.read()

                if record is not None:
                    records.append(record)
                elif time.monotonic() >= deadline:
                    results.put(("timeout", len(records)))
                    return
                else:
                    time.sleep(0.001)

        results.put(("ok", records))
    except Exception as exc:
        results.put(("error", repr(exc)))


def test_ring_buffer_can_be_opened_by_separate_process(tmp_path):
    path = tmp_path / "process-test.bin"
    count = 4
    context = multiprocessing.get_context("spawn")
    results = context.Queue()

    with RingBuffer(path, capacity=8, create=True):
        pass

    process = context.Process(
        target=_ring_buffer_producer,
        args=(str(path), count, results),
    )
    process.start()

    try:
        process.join(timeout=10)
        assert not process.is_alive(), "producer process timed out"
        assert process.exitcode == 0
        assert results.get(timeout=2) == ("ok", count)

        with RingBuffer(path, capacity=8) as ring:
            records = [ring.read() for _ in range(count)]

        assert all(record is not None for record in records)
        assert [record["timestamp_ns"] for record in records] == [
            i + 100 for i in range(count)
        ]
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        results.close()
        results.join_thread()


def test_ring_buffer_supports_concurrent_producer_and_consumer(tmp_path):
    path = tmp_path / "concurrent-test.bin"
    count = 100
    context = multiprocessing.get_context("spawn")
    results = context.Queue()

    with RingBuffer(path, capacity=8, create=True):
        pass

    consumer = context.Process(
        target=_ring_buffer_consumer,
        args=(str(path), count, results),
    )
    producer = context.Process(
        target=_ring_buffer_producer,
        args=(str(path), count, results),
    )

    consumer.start()
    producer.start()

    try:
        producer.join(timeout=20)
        consumer.join(timeout=20)

        assert not producer.is_alive(), "producer process timed out"
        assert not consumer.is_alive(), "consumer process timed out"
        assert producer.exitcode == 0
        assert consumer.exitcode == 0

        outcomes = [results.get(timeout=3), results.get(timeout=3)]
        errors = [outcome for outcome in outcomes if outcome[0] != "ok"]
        assert not errors, f"concurrent process errors: {errors}"

        records = next(
            outcome[1] for outcome in outcomes if outcome[0] == "ok"
            and isinstance(outcome[1], list)
        )
        assert len(records) == count
        assert [record["timestamp_ns"] for record in records] == [
            i + 100 for i in range(count)
        ]
    finally:
        for process in (producer, consumer):
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        results.close()
        results.join_thread()

import time
import pytest

from ipc.ring_buffer import RingBuffer


def test_write_and_read_record(tmp_path):
    path = tmp_path / "ticks.bin"

    with RingBuffer(path, capacity=4, create=True) as ring:
        assert ring.write(
            timestamp_ns=123,
            price_ticks=2500,
            quantity=3,
            side=1,
        )

        record = ring.read()

        assert record is not None
        assert record["timestamp_ns"] == 123
        assert record["price_ticks"] == 2500
        assert record["quantity"] == 3
        assert record["side"] == 1


def test_empty_buffer_returns_none(tmp_path):
    with RingBuffer(
        tmp_path / "ticks.bin",
        capacity=4,
        create=True,
    ) as ring:
        assert ring.read() is None


def test_full_buffer_and_wraparound(tmp_path):
    with RingBuffer(
        tmp_path / "ticks.bin",
        capacity=2,
        create=True,
    ) as ring:
        assert ring.write(
            timestamp_ns=1, price_ticks=100, quantity=1, side=1
        )
        assert ring.write(
            timestamp_ns=2, price_ticks=101, quantity=1, side=2
        )

        assert not ring.write(
            timestamp_ns=3, price_ticks=102, quantity=1, side=1
        )

        first = ring.read()
        assert first is not None
        assert first["timestamp_ns"] == 1

        assert ring.write(
            timestamp_ns=3, price_ticks=102, quantity=1, side=1
        )

        second = ring.read()
        third = ring.read()

        assert second is not None
        assert third is not None
        assert second["timestamp_ns"] == 2
        assert third["timestamp_ns"] == 3
        assert ring.read() is None


def test_invalid_tick_is_rejected(tmp_path):
    with RingBuffer(
        tmp_path / "ticks.bin",
        capacity=4,
        create=True,
    ) as ring:
        with pytest.raises(ValueError):
            ring.write(
                timestamp_ns=1,
                price_ticks=0,
                quantity=1,
                side=1,
            )


def test_reopen_existing_buffer_preserves_records(tmp_path):
    path = tmp_path / "ticks.bin"

    with RingBuffer(path, capacity=4, create=True) as ring:
        assert ring.write(
            timestamp_ns=123,
            price_ticks=2500,
            quantity=3,
            side=1,
        )

    with RingBuffer(path, capacity=4) as ring:
        record = ring.read()

        assert record is not None
        assert record["timestamp_ns"] == 123
        assert record["price_ticks"] == 2500
        assert record["quantity"] == 3
        assert record["side"] == 1


def test_reopening_with_different_capacity_is_rejected(tmp_path):
    path = tmp_path / "ticks.bin"

    with RingBuffer(path, capacity=4, create=True):
        pass

    with pytest.raises(ValueError, match="same capacity"):
        RingBuffer(path, capacity=2)


def test_capacity_less_than_two_is_rejected(tmp_path):
    path = tmp_path / "ticks.bin"

    with pytest.raises(ValueError, match="at least 2"):
        RingBuffer(path, capacity=1, create=True)


def test_write_releases_lock_when_operation_raises(tmp_path, monkeypatch):
    path = tmp_path / "lock-release.bin"

    with RingBuffer(path, capacity=4, create=True) as ring:
        original_counters = ring._counters

        def fail_counters():
            raise RuntimeError("simulated failure while holding lock")

        monkeypatch.setattr(ring, "_counters", fail_counters)

        with pytest.raises(RuntimeError, match="simulated failure"):
            ring.write(
                timestamp_ns=123,
                price_ticks=2500,
                quantity=1,
                side=1,
            )

        monkeypatch.setattr(ring, "_counters", original_counters)

        assert ring.write(
            timestamp_ns=124,
            price_ticks=2501,
            quantity=1,
            side=1,
        )

        record = ring.read()
        assert record is not None
        assert record["timestamp_ns"] == 124

import multiprocessing


def test_write_accepts_maximum_field_values(tmp_path):
    with RingBuffer(tmp_path / "max-values.bin", capacity=2, create=True) as ring:
        assert ring.write(
            timestamp_ns=(1 << 64) - 1,
            price_ticks=(1 << 32) - 1,
            quantity=(1 << 32) - 1,
            side=2,
        )
        record = ring.read()
        assert record is not None
        assert record["timestamp_ns"] == (1 << 64) - 1
        assert record["price_ticks"] == (1 << 32) - 1
        assert record["quantity"] == (1 << 32) - 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timestamp_ns", -1),
        ("timestamp_ns", 1 << 64),
        ("price_ticks", 0),
        ("price_ticks", 1 << 32),
        ("quantity", 0),
        ("quantity", 1 << 32),
        ("side", 0),
        ("side", 3),
        ("timestamp_ns", 1.5),
        ("price_ticks", True),
    ],
)
def test_write_rejects_invalid_field_values(tmp_path, field, value):
    values = {
        "timestamp_ns": 1,
        "price_ticks": 100,
        "quantity": 1,
        "side": 1,
    }
    values[field] = value
    with RingBuffer(tmp_path / "invalid-values.bin", capacity=2, create=True) as ring:
        with pytest.raises(ValueError):
            ring.write(**values)
def test_close_waits_for_active_read(tmp_path, monkeypatch):
    path = tmp_path / "close-active-read.bin"
    ring = RingBuffer(path, capacity=4, create=True)

    entered = threading.Event()
    release = threading.Event()
    read_errors = []
    close_errors = []

    original_counters = ring._counters

    def paused_counters():
        entered.set()
        if not release.wait(timeout=3):
            raise TimeoutError("test did not release paused read")
        return original_counters()

    monkeypatch.setattr(ring, "_counters", paused_counters)

    def reader():
        try:
            ring.read()
        except Exception as exc:
            read_errors.append(exc)

    def closer():
        try:
            ring.close()
        except Exception as exc:
            close_errors.append(exc)

    read_thread = threading.Thread(target=reader, daemon=True)
    close_thread = threading.Thread(target=closer, daemon=True)

    try:
        read_thread.start()
        assert entered.wait(timeout=2), "reader did not reach paused section"

        close_thread.start()
        close_thread.join(timeout=0.2)

        assert close_thread.is_alive(), (
            "close() returned while read() was still active"
        )

        release.set()
        read_thread.join(timeout=2)
        close_thread.join(timeout=2)

        assert not read_thread.is_alive(), "reader did not finish"
        assert not close_thread.is_alive(), "closer did not finish"
        assert not read_errors, f"read failed: {read_errors!r}"
        assert not close_errors, f"close failed: {close_errors!r}"
    finally:
        release.set()
        read_thread.join(timeout=2)
        close_thread.join(timeout=2)

        # Ensure resources are closed if the test fails before closer starts.
        if close_thread.ident is None:
            ring.close()


def test_operations_rejected_after_close(tmp_path):
    ring = RingBuffer(tmp_path / "closed-ring.bin", capacity=4, create=True)
    ring.close()

    with pytest.raises(RuntimeError, match="closing or closed"):
        ring.read()

    with pytest.raises(RuntimeError, match="closing or closed"):
        ring.write(
            timestamp_ns=123,
            price_ticks=2500,
            quantity=1,
            side=1,
        )


def test_concurrent_close_calls_are_safe(tmp_path):
    ring = RingBuffer(tmp_path / "concurrent-close.bin", capacity=4, create=True)
    entered_flush = threading.Event()
    release_flush = threading.Event()
    second_attempting = threading.Event()
    second_acquired = threading.Event()
    errors = []

    original_map = ring._map
    original_lifecycle = ring._lifecycle
    second_thread = None

    class LifecycleProxy:
        def __enter__(self):
            is_second = threading.current_thread() is second_thread
            if is_second:
                second_attempting.set()

            result = original_lifecycle.__enter__()

            if is_second:
                second_acquired.set()
            return result

        def __exit__(self, *args):
            return original_lifecycle.__exit__(*args)

        def __getattr__(self, name):
            return getattr(original_lifecycle, name)

    class MapProxy:
        def __getattr__(self, name):
            return getattr(original_map, name)

        def flush(self):
            entered_flush.set()
            if not release_flush.wait(timeout=5):
                raise TimeoutError("test did not release paused close")
            original_map.flush()

    ring._lifecycle = LifecycleProxy()
    ring._map = MapProxy()

    def closer():
        try:
            ring.close()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=closer, daemon=True)
    second_thread = threading.Thread(target=closer, daemon=True)

    try:
        first.start()
        assert entered_flush.wait(timeout=2), "first close did not reach flush"

        second_thread.start()
        assert second_attempting.wait(timeout=2), (
            "second close did not attempt to enter the lifecycle condition"
        )
        assert not second_acquired.wait(timeout=0.2), (
            "second close unexpectedly acquired the lifecycle condition "
            "while the first close was paused in flush"
        )

        release_flush.set()

        first.join(timeout=2)
        second_thread.join(timeout=2)

        assert not first.is_alive(), "first close did not finish"
        assert not second_thread.is_alive(), "second close did not finish"
        assert second_acquired.is_set(), "second close never acquired the condition"
        assert not errors, f"close failed: {errors!r}"
    finally:
        release_flush.set()
        first.join(timeout=2)
        second_thread.join(timeout=2)
def test_close_retries_after_map_close_failure(tmp_path):
    ring = RingBuffer(tmp_path / "close-failure.bin", capacity=4, create=True)
    original_map = ring._map

    class MapProxy:
        def __init__(self):
            self.close_calls = 0

        def __getattr__(self, name):
            return getattr(original_map, name)

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("simulated transient map close failure")
            original_map.close()

    proxy = MapProxy()
    ring._map = proxy

    try:
        with pytest.raises(OSError, match="simulated transient map close failure"):
            ring.close()

        assert not original_map.closed
        assert not ring._file.closed
        assert not ring._closed
        assert not ring._closing

        ring.close()

        assert original_map.closed
        assert ring._file.closed
        assert ring._closed
        assert not ring._closing
        assert proxy.close_calls == 2

        # Closing an already closed ring remains safe.
        ring.close()
    finally:
        if not original_map.closed:
            original_map.close()
        if not ring._file.closed:
            ring._file.close()



def test_concurrent_close_retries_after_cleanup_failure(tmp_path):
    ring = RingBuffer(
        tmp_path / "concurrent-close-failure.bin",
        capacity=4,
        create=True,
    )
    original_map = ring._map
    original_lifecycle = ring._lifecycle

    entered_map_close = threading.Event()
    release_failure = threading.Event()
    second_attempting = threading.Event()
    second_acquired = threading.Event()
    errors = []
    second_thread = None

    class LifecycleProxy:
        def __enter__(self):
            is_second = threading.current_thread() is second_thread
            if is_second:
                second_attempting.set()

            original_lifecycle.__enter__()

            if is_second:
                second_acquired.set()
            return self

        def __exit__(self, *args):
            return original_lifecycle.__exit__(*args)

        def __getattr__(self, name):
            return getattr(original_lifecycle, name)

    class MapProxy:
        def __init__(self):
            self.close_calls = 0

        def __getattr__(self, name):
            return getattr(original_map, name)

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                entered_map_close.set()
                if not release_failure.wait(timeout=5):
                    raise TimeoutError("test did not release failed close")
                raise OSError("simulated transient map close failure")
            original_map.close()

    proxy = MapProxy()
    ring._lifecycle = LifecycleProxy()
    ring._map = proxy

    def closer():
        try:
            ring.close()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=closer, daemon=True)
    second_thread = threading.Thread(target=closer, daemon=True)

    try:
        first.start()
        assert entered_map_close.wait(timeout=2), (
            "first close did not reach mmap.close()"
        )

        second_thread.start()
        assert second_attempting.wait(timeout=2), (
            "second close did not attempt to acquire the lifecycle lock"
        )
        assert not second_acquired.wait(timeout=0.2), (
            "second close acquired the lifecycle lock while cleanup was paused"
        )

        release_failure.set()

        first.join(timeout=3)
        second_thread.join(timeout=3)

        assert not first.is_alive(), "first close did not finish"
        assert not second_thread.is_alive(), "second close got stuck"
        assert second_acquired.is_set(), "second close never acquired the lock"
        assert len(errors) == 1
        assert isinstance(errors[0], OSError)
        assert str(errors[0]) == "simulated transient map close failure"
        assert original_map.closed
        assert ring._file.closed
        assert ring._closed
        assert not ring._closing
        assert proxy.close_calls == 2
    finally:
        release_failure.set()
        first.join(timeout=3)
        second_thread.join(timeout=3)
        if not original_map.closed:
            original_map.close()
        if not ring._file.closed:
            ring._file.close()
