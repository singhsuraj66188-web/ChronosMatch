"""Two-process IPC benchmark using the shared-memory RingBuffer.

Run from the repository root:

    python benchmarks/benchmark_ipc_1m.py
    python benchmarks/benchmark_ipc_1m.py --orders 1000000 --capacity 4096

Latency measures producer timestamp to consumer read. It includes
producer backpressure and queue waiting; it is not raw read/write latency.
"""

import argparse
import multiprocessing
import os
import queue
import sys
import tempfile
import time
from array import array


# Make "ipc" importable in this process and in spawned children.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHILD_TIMEOUT_SECONDS = 300
PARENT_TIMEOUT_SECONDS = 310

def validate_record(record, expected_sequence, previous_timestamp_ns, now_ns):
    """Return independent payload validation errors for one record."""
    sequence = record["sequence"]
    timestamp_ns = record["timestamp_ns"]
    price_ticks = record["price_ticks"]
    quantity = record["quantity"]
    side = record["side"]

    return {
        "sequence": (
            type(sequence) is not int
            or sequence != expected_sequence
        ),
        "timestamp": (
            type(timestamp_ns) is not int
            or timestamp_ns < 0
            or timestamp_ns > now_ns
            or (
                previous_timestamp_ns is not None
                and timestamp_ns < previous_timestamp_ns
            )
        ),
        "price_ticks": (
            type(price_ticks) is not int
            or price_ticks != expected_sequence + 1
        ),
        "quantity": type(quantity) is not int or quantity != 1,
        "side": type(side) is not int or side != 1,
    }




def producer(path, capacity, count, results):
    from ipc.ring_buffer import RingBuffer

    try:
        deadline = time.monotonic() + CHILD_TIMEOUT_SECONDS
        written = 0

        with RingBuffer(path, capacity=capacity) as ring:
            for i in range(count):
                timestamp_ns = time.perf_counter_ns()

                while not ring.write(
                    timestamp_ns=timestamp_ns,
                    price_ticks=i + 1,
                    quantity=1,
                    side=1,
                ):
                    if time.monotonic() >= deadline:
                        results.put(("producer", "timeout", written))
                        return

                written += 1

        results.put(("producer", "ok", written))

    except Exception as exc:
        results.put(("producer", "error", repr(exc)))


def consumer(path, capacity, count, results):
    from ipc.ring_buffer import RingBuffer

    try:
        latencies = array("q")
        payload_errors = {
            "sequence": 0,
            "timestamp": 0,
            "price_ticks": 0,
            "quantity": 0,
            "side": 0,
        }
        previous_timestamp_ns = None
        received = 0
        first_ns = None
        last_ns = None
        deadline = time.monotonic() + CHILD_TIMEOUT_SECONDS

        with RingBuffer(path, capacity=capacity) as ring:
            while received < count:
                record = ring.read()

                if record is None:
                    if time.monotonic() >= deadline:
                        results.put(("consumer", "timeout", received))
                        return
                    continue

                now = time.perf_counter_ns()

                if first_ns is None:
                    first_ns = now

                last_ns = now

                errors = validate_record(
                    record,
                    received,
                    previous_timestamp_ns,
                    now,
                )

                for field, has_error in errors.items():
                    if has_error:
                        payload_errors[field] += 1

                timestamp_ns = record["timestamp_ns"]
                if not errors["timestamp"]:
                    previous_timestamp_ns = timestamp_ns
                    latencies.append(now - timestamp_ns)

                received += 1

        ordered = sorted(latencies)
        n = len(ordered)

        p50_us = (
            ordered[min(n - 1, n // 2)] / 1000 if n else 0.0
        )
        p99_us = (
            ordered[min(n - 1, max(0, int(n * 0.99) - 1))] / 1000
            if n else 0.0
        )
        max_us = ordered[-1] / 1000 if n else 0.0

        consumer_interval = (
            (last_ns - first_ns) / 1e9 if received > 1 else 0.0
        )

        stats = {
            "received": received,
            "missing": max(0, count - received),
            "out_of_order": payload_errors["sequence"],
            "payload_errors": payload_errors,
            "consumer_interval_seconds": consumer_interval,
            "latency_samples": n,
            "p50_us": p50_us,
            "p99_us": p99_us,
            "max_us": max_us,
        }

        results.put(("consumer", "ok", stats))

    except Exception as exc:
        results.put(("consumer", "error", repr(exc)))


def benchmark_result(args_orders, written, stats, failed=False):
    """Return PASS only when every benchmark and payload check succeeds."""
    ok = (
        not failed
        and written == args_orders
        and stats["received"] == args_orders
        and stats["missing"] == 0
        and stats["out_of_order"] == 0
        and all(
            errors == 0
            for errors in stats["payload_errors"].values()
        )
    )
    return "PASS" if ok else "FAIL"


def main():
    parser = argparse.ArgumentParser(
        description="Two-process RingBuffer IPC benchmark."
    )
    parser.add_argument("--orders", type=int, default=1_000_000)
    parser.add_argument("--capacity", type=int, default=4096)
    args = parser.parse_args()

    if args.orders < 1:
        parser.error("--orders must be at least 1")

    if args.capacity < 2:
        parser.error("--capacity must be at least 2")

    from ipc.ring_buffer import RingBuffer

    context = multiprocessing.get_context("spawn")
    results = context.Queue()

    outcomes = {}
    processes = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ipc-benchmark.bin")

            with RingBuffer(path, capacity=args.capacity, create=True):
                pass

            cons = context.Process(
                target=consumer,
                args=(path, args.capacity, args.orders, results),
                name="ipc-consumer",
            )
            prod = context.Process(
                target=producer,
                args=(path, args.capacity, args.orders, results),
                name="ipc-producer",
            )

            processes = [cons, prod]

            start_ns = time.perf_counter_ns()

            cons.start()
            prod.start()

            deadline = time.monotonic() + PARENT_TIMEOUT_SECONDS

            while len(outcomes) < 2 and time.monotonic() < deadline:
                try:
                    who, status, payload = results.get(
                        timeout=min(1.0, max(0.1, deadline - time.monotonic()))
                    )
                    outcomes[who] = (status, payload)

                except queue.Empty:
                    if not any(process.is_alive() for process in processes):
                        break

            for process in processes:
                process.join(timeout=5)

                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

            total_seconds = (
                time.perf_counter_ns() - start_ns
            ) / 1e9

    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

        results.close()
        results.join_thread()

    failed = False

    for process in processes:
        if process.exitcode != 0:
            print(
                f"FAIL: {process.name} exited with code "
                f"{process.exitcode}"
            )
            failed = True

    for who in ("producer", "consumer"):
        if who not in outcomes:
            print(f"FAIL: {who} did not return a result")
            failed = True
            continue

        status, payload = outcomes[who]

        if status != "ok":
            print(f"FAIL: {who} -> {status}: {payload}")
            failed = True

    producer_result = outcomes.get("producer")
    consumer_result = outcomes.get("consumer")

    if (
        producer_result is None
        or consumer_result is None
        or producer_result[0] != "ok"
        or consumer_result[0] != "ok"
    ):
        print("RESULT: FAIL")
        sys.exit(1)

    written = producer_result[1]
    stats = consumer_result[1]

    received = stats["received"]
    missing = stats["missing"]
    out_of_order = stats["out_of_order"]

    throughput = (
        received / total_seconds if total_seconds > 0 else 0
    )

    print("\n========== IPC BENCHMARK RESULTS ==========")
    print(f"orders requested     : {args.orders:,}")
    print(f"orders written       : {written:,}")
    print(f"orders received      : {received:,}")
    print(f"missing orders       : {missing:,}")
    print(f"out of order         : {out_of_order:,}")
    print("payload validation errors:")
    for field, errors in stats["payload_errors"].items():
        print(f"  {field:20}: {errors:,}")
    print(f"total wall time      : {total_seconds:.2f} s")
    print(f"consumer drain time  : {stats['consumer_interval_seconds']:.2f} s")
    print(f"overall throughput   : {throughput:,.0f} orders/s")
    print(
        f"latency p50 / p99    : "
        f"{stats['p50_us']:.1f} us / {stats['p99_us']:.1f} us"
    )
    print(f"latency max          : {stats['max_us']:.1f} us")
    print("===========================================")

    result = benchmark_result(args.orders, written, stats, failed)

    print("RESULT:", result)
    sys.exit(0 if result == "PASS" else 1)


if __name__ == "__main__":
    main()
