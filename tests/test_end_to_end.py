import asyncio

from chronosmatch.matching_engine import MatchingEngine
from ipc.matching_consumer import process_record
from ipc.ring_buffer import RingBuffer
from simulator.market_simulator import Tick
from simulator.ring_buffer_integration import transfer_ticks


async def deterministic_ticks():
    """Produce a fixed sequence of simulated market events."""
    events = [
        Tick(
            sequence=0,
            timestamp_ns=100,
            symbol="SIM",
            price_ticks=100,
            quantity=5,
            side=1,  # BUY
        ),
        Tick(
            sequence=1,
            timestamp_ns=101,
            symbol="SIM",
            price_ticks=99,
            quantity=3,
            side=2,  # SELL
        ),
        Tick(
            sequence=2,
            timestamp_ns=102,
            symbol="SIM",
            price_ticks=100,
            quantity=4,
            side=2,  # SELL
        ),
    ]

    for event in events:
        yield event


def test_simulator_ring_buffer_matching_engine_end_to_end(tmp_path):
    async def run_pipeline():
        buffer_path = tmp_path / "e2e_ring_buffer.bin"

        with RingBuffer(buffer_path, capacity=8, create=True) as ring:
            result = await transfer_ticks(
                deterministic_ticks(),
                ring,
                poll_interval_ms=0.1,
            )

        return result

    result = asyncio.run(run_pipeline())

    # Every simulated event must pass through the ring buffer.
    assert result.metrics.successful_writes == 3
    assert result.metrics.successful_reads == 3
    assert result.metrics.failed_writes == 0

    records = result.transferred_ticks

    assert [record["simulator_sequence"] for record in records] == [
        0, 1, 2
    ]
    assert [record["sequence"] for record in records] == [0, 1, 2]

    assert [
        (
            record["timestamp_ns"],
            record["price_ticks"],
            record["quantity"],
            record["side"],
        )
        for record in records
    ] == [
        (100, 100, 5, 1),
        (101, 99, 3, 2),
        (102, 100, 4, 2),
    ]

    # Consume transferred records through the real IPC adapter.
    engine = MatchingEngine()
    trades = []

    for record in records:
        trades.extend(process_record(record, engine))

    # The first sell matches three units of the resting buy.
    # The second sell matches the remaining two units.
    assert [
        (
            trade.buy_order_id,
            trade.sell_order_id,
            trade.price,
            trade.quantity,
        )
        for trade in trades
    ] == [
        (1, 2, 100, 3),
        (1, 3, 100, 2),
    ]

    # The buy is fully filled; two units of the final sell remain.
    assert engine.bids == []
    assert len(engine.asks) == 1
    assert engine.asks[0].order_id == 3
    assert engine.asks[0].price == 100
    assert engine.asks[0].quantity == 2
    assert engine.active_order_ids == {3}
