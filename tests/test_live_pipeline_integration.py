import asyncio
import sqlite3

from chronosmatch.matching_engine import MatchingEngine
from ipc.ring_buffer import RingBuffer
from monitoring.latency_monitor import LatencyMonitor
from monitoring.live_dashboard import LiveDashboardState
from monitoring.trade_ledger import TradeLedger
from simulator.market_simulator import Tick
from simulator.ring_buffer_integration import transfer_ticks


def test_matching_pipeline_updates_ledger_and_dashboard(tmp_path):
    async def run_test():
        ring_path = tmp_path / "live-integration.dat"
        ledger_path = tmp_path / "live-trades.db"

        ticks = [
            Tick(
                sequence=0,
                timestamp_ns=1_000_000,
                symbol="SIM",
                price_ticks=100,
                quantity=5,
                side=2,  # SELL: rests in the ask book
            ),
            Tick(
                sequence=1,
                timestamp_ns=2_000_000,
                symbol="SIM",
                price_ticks=105,
                quantity=3,
                side=1,  # BUY: crosses the resting sell
            ),
        ]

        async def produce_ticks():
            for tick in ticks:
                yield tick

        engine = MatchingEngine()
        dashboard_latency = LatencyMonitor()
        dashboard_state = LiveDashboardState(engine, dashboard_latency)

        with TradeLedger(ledger_path) as ledger:
            with RingBuffer(ring_path, capacity=4, create=True) as ring:
                result = await transfer_ticks(
                    produce_ticks(),
                    ring,
                    engine=engine,
                    ledger=ledger,
                    dashboard_state=dashboard_state,
                )

            # Wait for the background SQLite worker to commit queued trades.
            ledger.flush()

            assert ledger.written == 1
            assert TradeLedger.count(ledger_path) == 1

            with sqlite3.connect(ledger_path) as connection:
                row = connection.execute(
                    """
                    SELECT ts_ns, buy_order_id, sell_order_id,
                           price_ticks, quantity
                    FROM trades
                    """
                ).fetchone()

            assert row == (2_000_000, 2, 1, 100, 3)

        snapshot = dashboard_state.snapshot()

        assert result.metrics.matching_processed_records == 2
        assert len(result.trades) == 1

        assert snapshot["last_trade"] == {
            "trade_id": 1,
            "buy_order_id": 2,
            "sell_order_id": 1,
            "price_ticks": 100,
            "quantity": 3,
            "levels_cleared": 1,
        }

        assert snapshot["asks"] == [(100, 2)]
        assert snapshot["bids"] == []
        assert snapshot["latency"]["count"] == 2
        assert snapshot["trades_per_s"] > 0

    asyncio.run(run_test())


def test_ledger_record_queues_without_synchronous_sqlite_write(tmp_path):
    ledger_path = tmp_path / "queued-trades.db"

    with TradeLedger(ledger_path) as ledger:
        ledger.record(
            price_ticks=100,
            quantity=2,
            buy_order_id=2,
            sell_order_id=1,
            ts_ns=2_000_000,
        )

        # Without flush(), the matching-path record() call does not wait
        # for a SQLite commit.
        assert ledger.written == 0
        assert TradeLedger.count(ledger_path) == 0

        ledger.flush()

        assert ledger.written == 1
        assert TradeLedger.count(ledger_path) == 1
