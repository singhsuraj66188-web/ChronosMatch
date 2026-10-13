
import asyncio
import math

import pytest

from monitoring.latency_monitor import LatencyMonitor
from simulator.market_simulator import generate_ticks


def collect_ticks(count=5, interval_ms=0, seed=1):
    async def collect():
        return [
            tick
            async for tick in generate_ticks(
                count=count,
                interval_ms=interval_ms,
                seed=seed,
            )
        ]

    return asyncio.run(collect())


def test_simulator_generates_requested_count():
    ticks = collect_ticks(count=5)

    assert len(ticks) == 5
    assert [tick.sequence for tick in ticks] == list(range(5))
    assert len({tick.sequence for tick in ticks}) == len(ticks)
    assert all(tick.price_ticks > 0 for tick in ticks)
    assert all(tick.quantity > 0 for tick in ticks)
    assert all(tick.side in (1, 2) for tick in ticks)


def test_simulator_zero_count_returns_no_ticks():
    assert collect_ticks(count=0) == []


def test_simulator_rejects_negative_count():
    with pytest.raises(ValueError):
        collect_ticks(count=-1)


@pytest.mark.parametrize("interval", [-1, math.nan, math.inf, -math.inf])
def test_simulator_rejects_invalid_intervals(interval):
    with pytest.raises(ValueError):
        collect_ticks(interval_ms=interval)


def test_simulator_accepts_zero_interval():
    assert len(collect_ticks(count=3, interval_ms=0)) == 3


def test_simulator_is_reproducible_with_same_seed():
    first = collect_ticks(count=10, seed=42)
    second = collect_ticks(count=10, seed=42)

    first_values = [
        (t.sequence, t.symbol, t.price_ticks, t.quantity, t.side)
        for t in first
    ]
    second_values = [
        (t.sequence, t.symbol, t.price_ticks, t.quantity, t.side)
        for t in second
    ]

    assert first_values == second_values


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
    assert result["p95_us"] == 0.0
    assert result["p99_us"] == 0.0


def test_latency_monitor_rejects_negative_duration():
    with pytest.raises(ValueError):
        LatencyMonitor().record(-1)


def test_latency_monitor_nearest_rank_p95_and_p99():
    monitor = LatencyMonitor(max_samples=100)

    for duration in range(1, 101):
        monitor.record(duration * 1000)

    result = monitor.summary()

    assert result["count"] == 100
    assert result["p95_us"] == 95.0
    assert result["p99_us"] == 99.0


def test_latency_monitor_keeps_bounded_sample_window():
    monitor = LatencyMonitor(max_samples=3)

    for duration in (1000, 2000, 3000, 4000):
        monitor.record(duration)

    result = monitor.summary()

    assert result["count"] == 3
    assert result["median_us"] == 3.0
    assert result["p95_us"] == 4.0
    assert result["p99_us"] == 4.0


def test_latency_monitor_accepts_zero_duration():
    monitor = LatencyMonitor()
    monitor.record(0)

    result = monitor.summary()

    assert result["count"] == 1
    assert result["median_us"] == 0.0
    assert result["p95_us"] == 0.0
    assert result["p99_us"] == 0.0


@pytest.mark.parametrize("max_samples", [0, -1])
def test_latency_monitor_rejects_invalid_window_size(max_samples):
    with pytest.raises(ValueError):
        LatencyMonitor(max_samples=max_samples)
