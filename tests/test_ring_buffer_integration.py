import asyncio

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

    asyncio.run(run_test())


def test_empty_input(tmp_path):
    async def run_test():
        path = tmp_path / "empty.dat"

        with RingBuffer(path, capacity=4, create=True) as ring:
            result = await transfer_ticks(
                generate_ticks(count=0, interval_ms=0),
                ring,
            )

        assert result.metrics.successful_writes == 0
        assert result.metrics.successful_reads == 0
        assert result.metrics.failed_writes == 0
        assert result.latency_sample_count == 0
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

    asyncio.run(run_test())


def test_retry_exhaustion_is_reported():
    class AlwaysFullBuffer:
        def write(self, **kwargs):
            return False

        def read(self):
            return None

    async def run_test():
        result = await transfer_ticks(
            generate_ticks(count=1, interval_ms=0),
            AlwaysFullBuffer(),
            max_retries=2,
            retry_interval_ms=1,
        )

        assert result.metrics.full_buffer_events == 3
        assert result.metrics.retry_attempts == 2
        assert result.metrics.failed_writes == 1
        assert result.metrics.successful_writes == 0
        assert result.metrics.successful_reads == 0
        assert result.latency_sample_count == 0

    asyncio.run(run_test())


def test_invalid_retry_configuration():
    class UnusedBuffer:
        def write(self, **kwargs):
            return True

        def read(self):
            return None

    async def run_test():
        try:
            await transfer_ticks(
                generate_ticks(count=0),
                UnusedBuffer(),
                max_retries=-1,
            )
        except ValueError:
            return

        raise AssertionError("Negative max_retries should raise ValueError")

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
