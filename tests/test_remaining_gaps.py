
import asyncio

import pytest

import simulator.market_simulator as market_simulator
from simulator.market_simulator import Tick
from simulator.ring_buffer_integration import transfer_ticks


def test_simulator_uses_perf_counter_ns_for_timestamp(monkeypatch):
    expected_timestamp = 123456789

    monkeypatch.setattr(
        market_simulator.time,
        "perf_counter_ns",
        lambda: expected_timestamp,
    )

    async def collect_one_tick():
        async for tick in market_simulator.generate_ticks(
            count=1,
            interval_ms=0,
            seed=1,
        ):
            return tick

    tick = asyncio.run(collect_one_tick())

    assert tick.timestamp_ns == expected_timestamp


def test_consumer_finishes_when_producer_raises():
    class TrackingBuffer:
        def __init__(self):
            self.records = []
            self.read_calls = 0

        def write(self, **kwargs):
            self.records.append({"sequence": 0, **kwargs})
            return True

        def read(self):
            self.read_calls += 1
            if self.records:
                return self.records.pop(0)
            return None

    async def run_test():
        buffer = TrackingBuffer()

        valid_tick = Tick(
            sequence=0,
            timestamp_ns=100,
            symbol="SIM",
            price_ticks=10000,
            quantity=1,
            side=1,
        )
        invalid_tick = Tick(
            sequence=1,
            timestamp_ns=200,
            symbol="OTHER",
            price_ticks=10100,
            quantity=1,
            side=2,
        )

        async def produce_ticks():
            yield valid_tick
            yield invalid_tick

        with pytest.raises(ValueError, match="only symbol SIM"):
            await transfer_ticks(produce_ticks(), buffer)

        assert buffer.read_calls >= 2
        assert buffer.records == []

    asyncio.run(run_test())
