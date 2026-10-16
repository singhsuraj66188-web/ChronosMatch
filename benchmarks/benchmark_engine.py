
import statistics
import time

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side


def percentile(values: list[int], p: int) -> float:
    """Return the nearest-rank percentile in microseconds."""
    ordered = sorted(values)
    index = max(0, (p * len(ordered) + 99) // 100 - 1)
    return ordered[index] / 1_000


def report(name: str, latencies_ns: list[int]) -> None:
    print(f"\n{name}")
    print(f"Samples:          {len(latencies_ns):,}")
    print(f"Median latency:   {statistics.median(latencies_ns) / 1_000:.2f} us")
    print(f"P95 latency:      {percentile(latencies_ns, 95):.2f} us")
    print(f"P99 latency:      {percentile(latencies_ns, 99):.2f} us")


def benchmark_non_crossing(iterations: int = 1000) -> list[int]:
    """Measure non-crossing buys inserted into a growing bid book."""
    engine = MatchingEngine()

    # Set up resting asks outside the timed region.
    for i in range(iterations):
        engine.submit_order(
            Order(
                order_id=i + 1,
                side=Side.SELL,
                price=20_000 + (i % 100),
                quantity=1,
                timestamp=i,
            )
        )

    latencies_ns = []

    for i in range(iterations):
        order = Order(
            order_id=iterations + i + 1,
            side=Side.BUY,
            price=10_000,
            quantity=1,
            timestamp=iterations + i,
        )

        start = time.perf_counter_ns()
        trades = engine.submit_order(order)
        elapsed = time.perf_counter_ns() - start

        if trades:
            raise AssertionError("Non-crossing order unexpectedly traded")

        latencies_ns.append(elapsed)

    return latencies_ns


def benchmark_crossing(iterations: int = 1000) -> list[int]:
    """Measure buys that each execute one trade against a resting ask."""
    engine = MatchingEngine()

    # Set up one unit of resting sell liquidity per incoming buy.
    for i in range(iterations):
        engine.submit_order(
            Order(
                order_id=i + 1,
                side=Side.SELL,
                price=10_000,
                quantity=1,
                timestamp=i,
            )
        )

    latencies_ns = []

    for i in range(iterations):
        order = Order(
            order_id=iterations + i + 1,
            side=Side.BUY,
            price=10_000,
            quantity=1,
            timestamp=iterations + i,
        )

        start = time.perf_counter_ns()
        trades = engine.submit_order(order)
        elapsed = time.perf_counter_ns() - start

        # Verify correctness outside the timed region.
        if len(trades) != 1:
            raise AssertionError(
                f"Expected exactly one trade, received {len(trades)}"
            )
        if trades[0].price != 10_000 or trades[0].quantity != 1:
            raise AssertionError("Unexpected trade price or quantity")

        latencies_ns.append(elapsed)

    if engine.asks:
        raise AssertionError("Some resting asks were unexpectedly left over")

    return latencies_ns


def main() -> None:
    iterations = 1_000

    print("ChronosMatch engine-only microbenchmark")
    print(f"Iterations per scenario: {iterations:,}")
    print("Setup is excluded from the timed region.")
    print("IPC and end-to-end pipeline latency are not measured.")

    non_crossing = benchmark_non_crossing(iterations)
    report("Scenario 1: Non-crossing submissions", non_crossing)

    crossing = benchmark_crossing(iterations)
    report("Scenario 2: Actual trade execution", crossing)


if __name__ == "__main__":
    main()
