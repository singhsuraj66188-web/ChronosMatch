
import asyncio

import pytest

from simulator.market_simulator import generate_ticks
from monitoring.latency_monitor import LatencyMonitor


def test_simulator_generates_requested_count():
    async def collect():
        return [
            tick
            async for tick in generate_ticks(
                count=5,
                interval_ms=0,
                seed=1,
            )
        ]

    ticks = asyncio.run(collect())

    assert len(ticks) == 5
    assert [tick.sequence for tick in ticks] == list(range(5))
    assert all(tick.price_ticks > 0 for tick in ticks)
    assert all(tick.quantity > 0 for tick in ticks)


def test_simulator_rejects_negative_count():
    async def collect():
        return [
            tick
            async for tick in generate_ticks(
                count=-1,
                interval_ms=0,
            )
        ]

    with pytest.raises(ValueError):
        asyncio.run(collect())


def test_latency_monitor_summary():
    monitor = LatencyMonitor()
    monitor.record(1000)
    monitor.record(2000)
    monitor.record(3000)

    result = monitor.summary()

    assert result["count"] == 3
    assert result["median_us"] == 2.0


def test_empty_latency_monitor():
    result = LatencyMonitor().summary()

    assert result["count"] == 0
    assert result["median_us"] == 0.0


def test_latency_monitor_rejects_negative_duration():
    monitor = LatencyMonitor()

    with pytest.raises(ValueError):
        monitor.record(-1)
