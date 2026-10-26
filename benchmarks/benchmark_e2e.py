
from __future__ import annotations

import argparse
import asyncio
import time

from chronosmatch.matching_engine import MatchingEngine
from ipc.ring_buffer import RingBuffer
from simulator.market_simulator import generate_ticks
from simulator.ring_buffer_integration import transfer_ticks


async def run_benchmark(
    count: int,
    capacity: int,
    poll_interval_ms: float,
    seed: int,
) -> None:
    # Use a fresh buffer for every benchmark run.
    buffer_path = ".e2e_benchmark_ring_buffer.bin"
    engine = MatchingEngine()

    start_ns = time.perf_counter_ns()

    with RingBuffer(buffer_path, capacity=capacity, create=True) as ring:
        result = await transfer_ticks(
            generate_ticks(count=count, interval_ms=0, seed=seed),
            ring,
            poll_interval_ms=poll_interval_ms,
            engine=engine,
        )

    elapsed_ns = time.perf_counter_ns() - start_ns

    metrics = result.metrics

    if metrics.successful_writes != count:
        raise AssertionError(
            f"Expected {count} writes, got {metrics.successful_writes}"
        )
    if metrics.successful_reads != count:
        raise AssertionError(
            f"Expected {count} reads, got {metrics.successful_reads}"
        )
    if metrics.failed_writes:
        raise AssertionError(
            f"Benchmark had {metrics.failed_writes} failed writes"
        )
    if result.latency_sample_count != count:
        raise AssertionError(
            f"Expected {count} pipeline latency samples, "
            f"got {result.latency_sample_count}"
        )

    pipeline_summary = result.latency_monitor.summary()
    matching_summary = result.matching_latency_monitor.summary()

    if matching_summary["count"] != count:
        raise AssertionError(
            f"Expected {count} matching-processing latency samples, "
            f"got {matching_summary['count']}"
        )

    elapsed_seconds = elapsed_ns / 1_000_000_000
    throughput = count / elapsed_seconds if elapsed_seconds > 0 else 0.0

    print("\nChronosMatch end-to-end pipeline benchmark")
    print("------------------------------------------")
    print(f"Generated ticks:                      {count:,}")
    print(f"Successful writes:                    {metrics.successful_writes:,}")
    print(f"Successful reads:                     {metrics.successful_reads:,}")
    print(f"Failed writes:                        {metrics.failed_writes:,}")
    print(f"Trades executed:                      {len(result.trades):,}")
    print(f"Total elapsed time:                   {elapsed_seconds:.6f} s")
    print(f"Pipeline throughput:                  {throughput:,.2f} ticks/s")

    print("\nProducer-start-to-consumer-read latency")
    print("---------------------------------------")
    print(f"Samples:                              {pipeline_summary['count']:,}")
    print(f"Median:                               {pipeline_summary['median_us']:.2f} us")
    print(f"P95:                                  {pipeline_summary['p95_us']:.2f} us")
    print(f"P99:                                  {pipeline_summary['p99_us']:.2f} us")

    print("\nMatching-processing latency")
    print("---------------------------")
    print(f"Samples:                              {matching_summary['count']:,}")
    print(f"Median:                               {matching_summary['median_us']:.2f} us")
    print(f"P95:                                  {matching_summary['p95_us']:.2f} us")
    print(f"P99:                                  {matching_summary['p99_us']:.2f} us")

    print("\nNotes:")
    print(
        "- Producer-start-to-consumer-read latency starts at the producer's "
        "initial tick-processing point and ends when the consumer reads "
        "the record; producer retries may contribute to this measurement."
    )
    print(
        "- Matching-processing latency measures the time spent inside "
        "process_record() for each record."
    )
    print(
        "- These are separate measurements. Neither should be presented "
        "as the complete end-to-end matching latency."
    )
    print("- Total elapsed time includes pipeline setup and shutdown.")
    print("- Synthetic ticks only; no real exchange data is used.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the ChronosMatch simulator-to-engine pipeline."
    )
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--capacity", type=int, default=2048)
    parser.add_argument("--poll-interval-ms", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.capacity < 2:
        parser.error("--capacity must be at least 2")
    if args.poll_interval_ms <= 0:
        parser.error("--poll-interval-ms must be positive")

    asyncio.run(
        run_benchmark(
            count=args.count,
            capacity=args.capacity,
            poll_interval_ms=args.poll_interval_ms,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()
