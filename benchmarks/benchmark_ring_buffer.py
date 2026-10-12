from __future__ import annotations

import argparse
import asyncio
import platform
import sys
import tempfile
from pathlib import Path

from ipc.ring_buffer import RingBuffer
from simulator.market_simulator import generate_ticks
from simulator.ring_buffer_integration import transfer_ticks


async def run_benchmark(
    count: int = 1000,
    capacity: int = 64,
    max_retries: int = 10,
    retry_interval_ms: float = 1.0,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        buffer_path = Path(directory) / "benchmark_ring.dat"

        with RingBuffer(
            buffer_path,
            capacity=capacity,
            create=True,
        ) as ring:
            result = await transfer_ticks(
                generate_ticks(count=count, interval_ms=0),
                ring,
                max_retries=max_retries,
                retry_interval_ms=retry_interval_ms,
            )

    metrics = result.metrics
    summary = result.latency_monitor.summary()

    successful = metrics.successful_reads
    elapsed_seconds = result.elapsed_ns / 1_000_000_000

    throughput = (
        successful / elapsed_seconds
        if elapsed_seconds > 0
        else 0.0
    )

    print("\nChronosMatch Ring Buffer Integration Benchmark")
    print("=" * 48)
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Operating system: {platform.platform()}")
    print(f"Processor: {platform.processor() or 'Not reported'}")
    print(f"Buffer capacity: {capacity}")
    print(f"Requested ticks: {count}")
    print(f"Successful writes: {metrics.successful_writes}")
    print(f"Successful reads: {successful}")
    print(f"Successful latency samples: {summary['count']}")
    print(f"Full-buffer events: {metrics.full_buffer_events}")
    print(f"Retry attempts: {metrics.retry_attempts}")
    print(f"Failed writes: {metrics.failed_writes}")
    print(f"Elapsed pipeline time: {elapsed_seconds:.6f} seconds")
    print(f"Successful-transfer throughput: {throughput:.2f} ticks/second")
    print(f"Median latency: {summary['median_us']:.2f} microseconds")
    print(f"P95 latency: {summary['p95_us']:.2f} microseconds")
    print(f"P99 latency: {summary['p99_us']:.2f} microseconds")
    print(
        f"Retry policy: {max_retries} retries, "
        f"{retry_interval_ms} ms interval"
    )
    print("\nNotes:")
    print("- Latency includes buffer transfer and consumer polling.")
    print("- Retry waits can substantially increase latency.")
    print(
        "- This measures a Python file-backed mmap prototype; "
        "it does not prove zero-copy or production HFT performance."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the ChronosMatch ring-buffer integration."
    )
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--capacity", type=int, default=64)
    parser.add_argument("--max-retries", type=int, default=10)
    parser.add_argument("--retry-interval-ms", type=float, default=1.0)

    args = parser.parse_args()

    if args.count < 0:
        parser.error("--count cannot be negative")
    if args.capacity < 2:
        parser.error("--capacity must be at least 2")
    if args.max_retries < 0:
        parser.error("--max-retries cannot be negative")
    if args.retry_interval_ms < 0:
        parser.error("--retry-interval-ms cannot be negative")

    asyncio.run(
        run_benchmark(
            count=args.count,
            capacity=args.capacity,
            max_retries=args.max_retries,
            retry_interval_ms=args.retry_interval_ms,
        )
    )


if __name__ == "__main__":
    main()
