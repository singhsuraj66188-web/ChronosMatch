from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Trade
from ipc.matching_consumer import process_record
from ipc.ring_buffer import RingBuffer
from monitoring.latency_monitor import LatencyMonitor
from simulator.market_simulator import Tick


@dataclass
class IntegrationMetrics:
    generated_ticks: int = 0
    successful_writes: int = 0
    successful_reads: int = 0
    matching_processed_records: int = 0
    full_buffer_events: int = 0
    retry_attempts: int = 0
    failed_writes: int = 0


@dataclass
class IntegrationResult:
    metrics: IntegrationMetrics
    transferred_ticks: list[dict[str, Any]] = field(
        default_factory=list
    )
    latency_monitor: LatencyMonitor = field(
        default_factory=LatencyMonitor
    )
    matching_latency_monitor: LatencyMonitor = field(
        default_factory=LatencyMonitor
    )
    matching_completion_latency_monitor: LatencyMonitor = field(
        default_factory=LatencyMonitor
    )
    elapsed_ns: int = 0
    trades: list[Trade] = field(default_factory=list)

    @property
    def latency_sample_count(self) -> int:
        return int(self.latency_monitor.summary()["count"])


async def transfer_ticks(
    ticks: AsyncIterator[Tick],
    ring: RingBuffer,
    *,
    max_retries: int = 10,
    retry_interval_ms: float = 1.0,
    poll_interval_ms: float = 0.1,
    engine: MatchingEngine | None = None,
) -> IntegrationResult:
    """Transfer SIM ticks through an existing, initially empty ring buffer.

    Each tick yielded by the input iterator increments generated_ticks.
    Each successful ring-buffer write increments successful_writes.
    Each record successfully read increments successful_reads.

    Simulator sequence numbers and timestamps must be strictly increasing.
    Invalid ordering is rejected before the tick is written to the buffer.

    matching_processed_records counts records for which process_record()
    returns successfully when a matching engine is provided. A successfully
    processed record does not necessarily produce a trade.

    Each tick receives one initial write attempt and at most max_retries
    additional attempts. Failed writes are counted and never reported as
    successful transfers.

    The existing binary record format is unchanged. The SIM symbol and
    simulator sequence are tracked separately because they are not stored
    in the ring-buffer record.

    latency_monitor measures from the producer's initial tick-processing
    point until the consumer reads the record.

    matching_latency_monitor measures only the time spent processing each
    record through process_record() when a matching engine is provided.

    matching_completion_latency_monitor measures from the producer's
    initial tick-processing point until process_record() finishes. This
    includes time waiting for the consumer to read the record. Samples are
    recorded only when a matching engine is provided.

    If pipeline processing raises an exception, this function propagates
    the exception rather than returning a partial IntegrationResult.
    """
    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise TypeError("max_retries must be an integer")

    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")

    if (
        not math.isfinite(retry_interval_ms)
        or retry_interval_ms < 0
    ):
        raise ValueError(
            "retry_interval_ms must be finite and non-negative"
        )

    if (
        not math.isfinite(poll_interval_ms)
        or poll_interval_ms <= 0
    ):
        raise ValueError(
            "poll_interval_ms must be finite and positive"
        )

    metrics = IntegrationMetrics()
    result = IntegrationResult(metrics=metrics)
    producer_done = asyncio.Event()

    start_times: dict[int, int] = {}
    simulator_sequences: dict[int, int] = {}
    next_buffer_sequence = 0
    start_ns = time.perf_counter_ns()

    async def consume() -> None:
        while True:
            record = ring.read()

            if record is None:
                if producer_done.is_set():
                    return

                await asyncio.sleep(poll_interval_ms / 1000)
                continue

            buffer_sequence = record["sequence"]

            started_ns = start_times.pop(
                buffer_sequence, None
            )
            simulator_sequence = simulator_sequences.pop(
                buffer_sequence, None
            )

            if (
                started_ns is None
                or simulator_sequence is None
            ):
                raise RuntimeError(
                    "Unexpected ring-buffer record. "
                    "Use an empty buffer for each integration run."
                )

            latency_ns = time.perf_counter_ns() - started_ns
            result.latency_monitor.record(latency_ns)
            metrics.successful_reads += 1

            result.transferred_ticks.append(
                {
                    "simulator_sequence": simulator_sequence,
                    "symbol": "SIM",
                    **record,
                }
            )

            if engine is not None:
                matching_started_ns = time.perf_counter_ns()

                # Count a record as processed only if process_record()
                # completes successfully.
                matching_trades = process_record(record, engine)

                matching_completed_ns = time.perf_counter_ns()

                metrics.matching_processed_records += 1
                result.trades.extend(matching_trades)

                matching_latency_ns = (
                    matching_completed_ns - matching_started_ns
                )
                result.matching_latency_monitor.record(
                    matching_latency_ns
                )

                result.matching_completion_latency_monitor.record(
                    matching_completed_ns - started_ns
                )

    consumer_task = asyncio.create_task(consume())

    async def produce() -> None:
        nonlocal next_buffer_sequence

        last_simulator_sequence: int | None = None
        last_timestamp_ns: int | None = None

        async for tick in ticks:
            # This counts ticks yielded by the source iterator,
            # including ticks later rejected by validation.
            metrics.generated_ticks += 1

            if consumer_task.done():
                consumer_task.result()

            if tick.symbol != "SIM":
                raise ValueError(
                    "This initial integration supports only symbol SIM"
                )

            # Simulator sequence numbers must strictly increase.
            if (
                last_simulator_sequence is not None
                and tick.sequence <= last_simulator_sequence
            ):
                raise ValueError(
                    "Simulator sequence must be strictly increasing"
                )

            # Simulator timestamps must strictly increase.
            if (
                last_timestamp_ns is not None
                and tick.timestamp_ns <= last_timestamp_ns
            ):
                raise ValueError(
                    "timestamp_ns must be strictly increasing"
                )

            tick_started_ns = time.perf_counter_ns()
            retries_used = 0

            while True:
                if consumer_task.done():
                    consumer_task.result()

                written = ring.write(
                    timestamp_ns=tick.timestamp_ns,
                    price_ticks=tick.price_ticks,
                    quantity=tick.quantity,
                    side=tick.side,
                )

                if written:
                    start_times[next_buffer_sequence] = (
                        tick_started_ns
                    )
                    simulator_sequences[next_buffer_sequence] = (
                        tick.sequence
                    )
                    next_buffer_sequence += 1

                    metrics.successful_writes += 1

                    # Update ordering baselines only after a successful write.
                    last_simulator_sequence = tick.sequence
                    last_timestamp_ns = tick.timestamp_ns

                    break

                metrics.full_buffer_events += 1

                if retries_used >= max_retries:
                    metrics.failed_writes += 1
                    raise RuntimeError(
                        f"Ring-buffer write failed after "
                        f"{retries_used + 1} attempts"
                    )

                retries_used += 1
                metrics.retry_attempts += 1

                await asyncio.sleep(
                    retry_interval_ms / 1000
                )

            await asyncio.sleep(0)

    producer_task = asyncio.create_task(produce())
    producer_error = None

    try:
        await asyncio.wait(
            {producer_task, consumer_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # A consumer read failure takes priority, even if both tasks finished.
        if consumer_task.done():
            if consumer_task.cancelled():
                raise asyncio.CancelledError()

            consumer_error = consumer_task.exception()

            if consumer_error is not None:
                if not producer_task.done():
                    producer_task.cancel()

                try:
                    await producer_task
                except BaseException:
                    pass

                raise consumer_error

        # The producer finished first. Preserve accepted records by draining.
        try:
            await producer_task
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            producer_error = exc

        producer_done.set()

        try:
            await consumer_task
        except BaseException:
            if producer_error is None:
                raise

        if producer_error is not None:
            raise producer_error

    finally:
        producer_done.set()

        if not producer_task.done():
            producer_task.cancel()

        try:
            await producer_task
        except BaseException:
            # Cleanup must not mask the selected pipeline exception.
            pass

        if not consumer_task.done():
            try:
                await consumer_task
            except BaseException:
                pass

    result.elapsed_ns = time.perf_counter_ns() - start_ns

    if metrics.successful_writes != metrics.successful_reads:
        raise RuntimeError(
            "Pipeline mismatch: successful writes and reads differ"
        )

    return result