
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

    # Reconcile the expected number of records across the pipeline.
    expected_counts = {
        "generated ticks": metrics.generated_ticks,
        "successful writes": metrics.successful_writes,
        "successful reads": metrics.successful_reads,
        "matching-processed records": metrics.matching_processed_records,
    }

    for metric_name, actual_count in expected_counts.items():
        if actual_count != count:
            raise AssertionError(
                f"Expected {count} {metric_name}, got {actual_count}"
            )

    if metrics.failed_writes:
        raise AssertionError(
            f"Benchmark had {metrics.failed_writes} failed writes"
        )

    if result.latency_sample_count != count:
        raise AssertionError(
            f"Expected {count} producer-to-read latency samples, "
            f"got {result.latency_sample_count}"
        )

    pipeline_summary = result.latency_monitor.summary()
    matching_summary = result.matching_latency_monitor.summary()
    completion_summary = (
        result.matching_completion_latency_monitor.summary()
    )

    if matching_summary["count"] != count:
        raise AssertionError(
            f"Expected {count} matching-processing latency samples, "
            f"got {matching_summary['count']}"
        )

    if completion_summary["count"] != count:
        raise AssertionError(
            f"Expected {count} matching-completion latency samples, "
            f"got {completion_summary['count']}"
        )

    elapsed_seconds = elapsed_ns / 1_000_000_000
    throughput = count / elapsed_seconds if elapsed_seconds > 0 else 0.0

    print("\nChronosMatch end-to-end pipeline benchmark")
    print("------------------------------------------")
    print(f"Generated ticks:                      {metrics.generated_ticks:,}")
    print(f"Successful writes:                    {metrics.successful_writes:,}")
    print(f"Successful reads:                     {metrics.successful_reads:,}")
    print(
        f"Matching-processed records:           "
        f"{metrics.matching_processed_records:,}"
    )
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

    print("\nProducer-start-to-matching-completion latency")
    print("---------------------------------------------")
    print(f"Samples:                              {completion_summary['count']:,}")
    print(f"Median:                               {completion_summary['median_us']:.2f} us")
    print(f"P95:                                  {completion_summary['p95_us']:.2f} us")
    print(f"P99:                                  {completion_summary['p99_us']:.2f} us")

    print("\nNotes:")
    print(
        "- Producer-start-to-consumer-read latency ends when the consumer "
        "reads the record; producer retries may contribute."
    )
    print(
        "- Matching-processing latency measures only process_record() "
        "execution."
    )
    print(
        "- Producer-start-to-matching-completion latency begins when the "
        "producer starts processing a yielded tick and ends when "
        "process_record() returns. It includes waiting for the consumer."
    )
    print(
        "- The matching-completion metric is a per-record measurement, "
        "not total batch elapsed time."
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
