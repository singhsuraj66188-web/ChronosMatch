import asyncio

import pytest

from chronosmatch.matching_engine import MatchingEngine
from ipc.ring_buffer import RingBuffer
from simulator.market_simulator import Tick, generate_ticks
from simulator.ring_buffer_integration import transfer_ticks


def test_successful_transfers_preserve_values_and_order(tmp_path):
    async def run_test():
        path = tmp_path / "integration.dat"

        original_ticks = [
            Tick(
                sequence=i,
                timestamp_ns=1_000_000 + i,
                symbol="SIM",
                price_ticks=10_000 + i,
                quantity=i + 1,
                side=1 if i % 2 == 0 else 2,
            )
            for i in range(20)
        ]

        async def produce_ticks():
            for tick in original_ticks:
                yield tick

        with RingBuffer(path, capacity=4, create=True) as ring:
            result = await transfer_ticks(produce_ticks(), ring)

        assert result.metrics.successful_writes == 20
        assert result.metrics.successful_reads == 20
        assert result.metrics.failed_writes == 0
        assert result.latency_sample_count == 20

        transferred = result.transferred_ticks
        assert len(transferred) == len(original_ticks)

        for original, received in zip(original_ticks, transferred):
            assert received["simulator_sequence"] == original.sequence
            assert received["sequence"] == original.sequence
            assert received["symbol"] == original.symbol
            assert received["timestamp_ns"] == original.timestamp_ns
            assert received["price_ticks"] == original.price_ticks
            assert received["quantity"] == original.quantity
            assert received["side"] == original.side

        assert [
            tick["simulator_sequence"] for tick in transferred
        ] == list(range(20))

        # No matching engine was supplied, so no matching samples are recorded.
        assert result.matching_latency_monitor.summary()["count"] == 0

    asyncio.run(run_test())


def test_empty_input(tmp_path):
    async def run_test():
        path = tmp_path / "empty.dat"

        with RingBuffer(path, capacity=4, create=True) as ring:
            result = await transfer_ticks(
                generate_ticks(count=0, interval_ms=0),
                ring,
                engine=MatchingEngine(),
            )

        assert result.metrics.successful_writes == 0
        assert result.metrics.successful_reads == 0
        assert result.metrics.failed_writes == 0
        assert result.latency_sample_count == 0
        assert result.matching_latency_monitor.summary()["count"] == 0
        assert result.transferred_ticks == []

    asyncio.run(run_test())


def test_full_buffer_preserves_unread_records(tmp_path):
    path = tmp_path / "full.dat"

    with RingBuffer(path, capacity=2, create=True) as ring:
        assert ring.write(
            timestamp_ns=100,
            price_ticks=101,
            quantity=2,
            side=1,
        )

        assert ring.write(
            timestamp_ns=200,
            price_ticks=102,
            quantity=3,
            side=2,
        )

        assert not ring.write(
            timestamp_ns=300,
            price_ticks=103,
            quantity=4,
            side=1,
        )

        assert ring.read() == {
            "sequence": 0,
            "timestamp_ns": 100,
            "price_ticks": 101,
            "quantity": 2,
            "side": 1,
        }

        assert ring.read() == {
            "sequence": 1,
            "timestamp_ns": 200,
            "price_ticks": 102,
            "quantity": 3,
            "side": 2,
        }

        assert ring.read() is None


def test_retry_then_success():
    class RetryBuffer:
        def __init__(self):
            self.failures_remaining = 2
            self.records = []

        def write(self, **kwargs):
            if self.failures_remaining > 0:
                self.failures_remaining -= 1
                return False

            self.records.append({"sequence": 0, **kwargs})
            return True

        def read(self):
            if self.records:
                return self.records.pop(0)
            return None

    async def run_test():
        result = await transfer_ticks(
            generate_ticks(count=1, interval_ms=0),
            RetryBuffer(),
            max_retries=3,
            retry_interval_ms=1,
        )

        assert result.metrics.successful_writes == 1
        assert result.metrics.successful_reads == 1
        assert result.metrics.full_buffer_events == 2
        assert result.metrics.retry_attempts == 2
        assert result.metrics.failed_writes == 0
        assert result.latency_sample_count == 1
        assert result.matching_latency_monitor.summary()["count"] == 0

    asyncio.run(run_test())


def test_retry_exhaustion_is_reported():
    class AlwaysFullBuffer:
        def __init__(self):
            self.write_calls = 0

        def write(self, **kwargs):
            self.write_calls += 1
            return False

        def read(self):
            return None

    async def run_test():
        buffer = AlwaysFullBuffer()

        with pytest.raises(
            RuntimeError,
            match="Ring-buffer write failed after 3 attempts",
        ):
            await transfer_ticks(
                generate_ticks(count=1, interval_ms=0),
                buffer,
                max_retries=2,
                retry_interval_ms=1,
            )

        assert buffer.write_calls == 3

    asyncio.run(run_test())


def test_invalid_retry_configuration():
    class UnusedBuffer:
        def write(self, **kwargs):
            return True

        def read(self):
            return None

    # Keep the rest of your existing test code here.


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("retry_interval_ms", float("nan")),
        ("retry_interval_ms", float("inf")),
        ("retry_interval_ms", float("-inf")),
        ("poll_interval_ms", float("nan")),
        ("poll_interval_ms", float("inf")),
        ("poll_interval_ms", float("-inf")),
    ],
)
def test_integration_rejects_non_finite_timing_intervals(
    parameter, value
):
    class UnusedBuffer:
        def write(self, **kwargs):
            return True

        def read(self):
            return None

    async def run_test():
        kwargs = {parameter: value}

        with pytest.raises(ValueError, match=parameter):
            await transfer_ticks(
                generate_ticks(count=0),
                UnusedBuffer(),
                **kwargs,
            )

    asyncio.run(run_test())

def test_ring_buffer_cleanup(tmp_path):
    path = tmp_path / "cleanup.dat"

    with RingBuffer(path, capacity=2, create=True) as ring:
        assert ring.write(
            timestamp_ns=100,
            price_ticks=101,
            quantity=1,
            side=1,
        )

    path.unlink()
    assert not path.exists()


def test_simulator_ticks_reach_matching_engine_and_create_trade(tmp_path):
    async def run_test():
        path = tmp_path / "matching-integration.dat"
        engine = MatchingEngine()

        ticks = [
            Tick(
                sequence=0,
                timestamp_ns=100,
                symbol="SIM",
                price_ticks=10000,
                quantity=2,
                side=2,  # SELL
            ),
            Tick(
                sequence=1,
                timestamp_ns=200,
                symbol="SIM",
                price_ticks=10100,
                quantity=1,
                side=1,  # BUY
            ),
        ]

        async def produce_ticks():
            for tick in ticks:
                yield tick

        with RingBuffer(path, capacity=4, create=True) as ring:
            result = await transfer_ticks(
                produce_ticks(),
                ring,
                engine=engine,
            )

        assert result.metrics.successful_writes == 2
        assert result.metrics.successful_reads == 2
        assert len(result.trades) == 1

        # One matching-processing latency sample per processed record.
        assert result.matching_latency_monitor.summary()["count"] == 2

        trade = result.trades[0]
        assert trade.buy_order_id == 2
        assert trade.sell_order_id == 1
        assert trade.price == 10000
        assert trade.quantity == 1

        assert len(engine.asks) == 1
        assert engine.asks[0].quantity == 1
        assert engine.bids == []

    asyncio.run(run_test())


def test_consumer_shutdown_drains_buffer_after_value_error():
    class TrackingBuffer:
        def __init__(self):
            self.records = []
            self.read_calls = 0
            self.next_sequence = 0

        def write(self, **kwargs):
            self.records.append(
                {"sequence": self.next_sequence, **kwargs}
            )
            self.next_sequence += 1
            return True

        def read(self):
            self.read_calls += 1

            if self.records:
                return self.records.pop(0)

            return None

    async def run_test():
        buffer = TrackingBuffer()

        ticks = [
            Tick(
                sequence=0,
                timestamp_ns=100,
                symbol="SIM",
                price_ticks=10000,
                quantity=1,
                side=1,
            ),
            Tick(
                sequence=1,
                timestamp_ns=200,
                symbol="INVALID",
                price_ticks=10100,
                quantity=1,
                side=2,
            ),
        ]

        async def produce_ticks():
            for tick in ticks:
                yield tick

        with pytest.raises(ValueError, match="only symbol SIM"):
            await transfer_ticks(produce_ticks(), buffer)

        assert buffer.read_calls >= 2
        assert buffer.records == []

    asyncio.run(run_test())


def test_consumer_failure_propagates_without_consuming_remaining_ticks():
    class FailingConsumerBuffer:
        def __init__(self):
            self.write_calls = 0
            self.read_calls = 0

        def write(self, **kwargs):
            self.write_calls += 1
            return True

        def read(self):
            self.read_calls += 1
            raise RuntimeError("simulated consumer failure")

    async def run_test():
        buffer = FailingConsumerBuffer()
        yielded_sequences = []

        async def produce_ticks():
            for i in range(5):
                yielded_sequences.append(i)
                yield Tick(
                    sequence=i,
                    timestamp_ns=100 + i,
                    symbol="SIM",
                    price_ticks=10_000 + i,
                    quantity=1,
                    side=1,
                )

        with pytest.raises(
            RuntimeError, match="simulated consumer failure"
        ):
            await transfer_ticks(
                produce_ticks(),
                buffer,
                retry_interval_ms=1,
            )

        assert buffer.read_calls == 1
        assert buffer.write_calls <= 1
        assert len(yielded_sequences) <= 1

    asyncio.run(run_test())


def test_original_processing_error_is_preserved_when_consumer_cleanup_fails():
    class CleanupFailingBuffer:
        def __init__(self):
            self.read_calls = 0

        def write(self, **kwargs):
            return True

        def read(self):
            self.read_calls += 1
            if self.read_calls == 1:
                return None
            raise RuntimeError("cleanup failure")

    async def run_test():
        buffer = CleanupFailingBuffer()

        async def produce_ticks():
            raise ValueError("original processing failure")
            yield  # Make this an async generator.

        with pytest.raises(
            ValueError, match="original processing failure"
        ):
            await transfer_ticks(produce_ticks(), buffer)

        assert buffer.read_calls >= 1

    asyncio.run(run_test())


def test_matching_latency_is_not_recorded_without_engine(tmp_path):
    async def run_test():
        path = tmp_path / "without-engine.dat"

        ticks = [
            Tick(
                sequence=0,
                timestamp_ns=100,
                symbol="SIM",
                price_ticks=10000,
                quantity=1,
                side=1,
            ),
            Tick(
                sequence=1,
                timestamp_ns=200,
                symbol="SIM",
                price_ticks=10100,
                quantity=1,
                side=2,
            ),
        ]

        async def produce_ticks():
            for tick in ticks:
                yield tick

        with RingBuffer(path, capacity=4, create=True) as ring:
            result = await transfer_ticks(produce_ticks(), ring)

        assert result.metrics.successful_reads == 2
        assert result.latency_sample_count == 2
        assert result.matching_latency_monitor.summary()["count"] == 0

    asyncio.run(run_test())


def test_matching_latency_samples_match_processed_records(tmp_path):
    async def run_test():
        path = tmp_path / "matching-latency.dat"
        engine = MatchingEngine()

        ticks = [
            Tick(
                sequence=0,
                timestamp_ns=100,
                symbol="SIM",
                price_ticks=10500,
                quantity=1,
                side=2,  # SELL
            ),
            Tick(
                sequence=1,
                timestamp_ns=200,
                symbol="SIM",
                price_ticks=10000,
                quantity=1,
                side=1,  # BUY
            ),
            Tick(
                sequence=2,
                timestamp_ns=300,
                symbol="SIM",
                price_ticks=10500,
                quantity=1,
                side=1,  # BUY
            ),
        ]

        async def produce_ticks():
            for tick in ticks:
                yield tick

        with RingBuffer(path, capacity=4, create=True) as ring:
            result = await transfer_ticks(
                produce_ticks(),
                ring,
                engine=engine,
            )

        assert result.metrics.successful_reads == 3
        assert result.matching_latency_monitor.summary()["count"] == 3

    asyncio.run(run_test())