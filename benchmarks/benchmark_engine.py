import statistics
import time

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side


def run_benchmark(iterations: int = 1000) -> None:
    engine = MatchingEngine()

    # Build a growing sell book before measuring.
    # These asks are deliberately priced above the incoming buy orders.
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

    latencies_ns: list[int] = []

    # Each buy does not cross the sell book.
    # The engine must process an increasingly large opposite-side book.
    for i in range(iterations):
        order = Order(
            order_id=iterations + i + 1,
            side=Side.BUY,
            price=10_000,
            quantity=1,
            timestamp=iterations + i,
        )

        start = time.perf_counter_ns()
        engine.submit_order(order)
        latencies_ns.append(time.perf_counter_ns() - start)

    ordered = sorted(latencies_ns)

    def percentile(p: float) -> float:
        index = min(int((p / 100) * len(ordered)), len(ordered) - 1)
        return ordered[index] / 1_000

    print(f"Resting asks:     {iterations:,}")
    print(f"Buy submissions:  {iterations:,}")
    print(f"Median latency:   {statistics.median(ordered) / 1_000:.2f} µs")
    print(f"P95 latency:      {percentile(95):.2f} µs")
    print(f"P99 latency:      {percentile(99):.2f} µs")
    print("Scenario: non-crossing buys against a growing sell book.")
    print("This is a microbenchmark, not end-to-end IPC latency.")


if __name__ == "__main__":
    run_benchmark()