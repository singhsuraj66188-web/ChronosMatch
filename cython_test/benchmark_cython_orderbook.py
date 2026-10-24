from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side

import importlib

# Add this file's directory so the compiled extension can be imported whether
# the benchmark is run as a script or as a module.
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    cython_orderbook = importlib.import_module("cython_orderbook")
except ImportError as exc:
    try:
        cython_orderbook = importlib.import_module("cython_test.cython_orderbook")
    except ImportError:
        raise ImportError(
            "Could not import cython_orderbook. Build it before running this benchmark."
        ) from exc

OrderBook = cython_orderbook.OrderBook

ITERATIONS = 5000
BATCHES = 5
WARMUP = 200

# Same four-order workload for both implementations.
ORDERS = [
    ("SELL", 100, 10),
    ("BUY", 100, 6),
    ("BUY", 100, 8),
    ("SELL", 100, 4),
]


def python_scenario():
    engine = MatchingEngine()
    trace = []

    for order_id, (side, price, quantity) in enumerate(ORDERS, start=1):
        order = Order(
            order_id=order_id,
            side=Side(side),
            price=price,
            quantity=quantity,
        )
        fills = engine.submit_order(order)
        trace.extend(
            (trade.price, trade.quantity, side)
            for trade in fills
        )

    return trace


def cython_scenario():
    book = OrderBook()
    trace = []

    for side, price, quantity in ORDERS:
        trace.extend(book.add_order(side, price, quantity))

    return trace


def run_python_timed():
    engine = MatchingEngine()

    engine.submit_order(Order(1, Side.SELL, 100, 10))
    engine.submit_order(Order(2, Side.BUY, 100, 6))
    engine.submit_order(Order(3, Side.BUY, 100, 8))
    engine.submit_order(Order(4, Side.SELL, 100, 4))


def run_cython_timed():
    book = OrderBook()

    book.add_order("SELL", 100, 10)
    book.add_order("BUY", 100, 6)
    book.add_order("BUY", 100, 8)
    book.add_order("SELL", 100, 4)


def percentile(values, percent):
    ordered = sorted(values)
    index = max(0, (len(ordered) * percent + 99) // 100 - 1)
    return ordered[index]


def measure(function, iterations):
    samples = []

    for _ in range(iterations):
        start = time.perf_counter_ns()
        function()
        samples.append(time.perf_counter_ns() - start)

    return samples


def report(label, samples):
    print(
        f"{label}: n={len(samples)}, "
        f"median={statistics.median(samples):.0f} ns, "
        f"P95={percentile(samples, 95)} ns, "
        f"P99={percentile(samples, 99)} ns"
    )


if __name__ == "__main__":
    print(f"Python: {sys.version.split()[0]}")
    print(f"Cython: {__import__('Cython').__version__}")
    print(f"Workload: {len(ORDERS)} orders per fresh book")
    print(f"Batches: {BATCHES}; iterations per batch: {ITERATIONS}")
    print(f"Warm-up calls per implementation: {WARMUP}")

    expected = [
        (100, 6, "BUY"),
        (100, 4, "BUY"),
        (100, 4, "SELL"),
    ]

    python_trace = python_scenario()
    cython_trace = cython_scenario()

    print("\nCorrectness check:")
    print("Python trace:", python_trace)
    print("Cython trace:", cython_trace)

    if python_trace != cython_trace:
        raise SystemExit("FAIL: matching traces differ; benchmark aborted.")

    if python_trace != expected:
        raise SystemExit("FAIL: unexpected trade trace; benchmark aborted.")

    print("PASS: both implementations produced the expected trade trace.")

    for _ in range(WARMUP):
        run_python_timed()
        run_cython_timed()

    python_samples = []
    cython_samples = []

    for batch in range(BATCHES):
        # Alternate order to reduce systematic first/second bias.
        if batch % 2 == 0:
            python_samples.extend(measure(run_python_timed, ITERATIONS))
            cython_samples.extend(measure(run_cython_timed, ITERATIONS))
        else:
            cython_samples.extend(measure(run_cython_timed, ITERATIONS))
            python_samples.extend(measure(run_python_timed, ITERATIONS))

        print(f"Completed batch {batch + 1}/{BATCHES}")

    print("\nAggregate results:")
    report("Python reference", python_samples)
    report("Cython prototype", cython_samples)

    python_median = statistics.median(python_samples)
    cython_median = statistics.median(cython_samples)

    print(f"Median ratio (Python/Cython): {python_median / cython_median:.2f}x")
    print(
        "Median reduction: "
        f"{(1 - cython_median / python_median) * 100:.1f}%"
    )

    print(
        "\nCaveat: this is a small local microbenchmark, not an end-to-end "
        "latency measurement. The implementations have different APIs, "
        "trade representations, and feature coverage."
    )
