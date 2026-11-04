from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side, Trade
from monitoring.latency_monitor import LatencyMonitor
from monitoring.live_dashboard import LiveDashboardState


def test_snapshot_contains_order_book_and_latency():
    engine = MatchingEngine()
    engine.submit_order(
        Order(
            order_id=1,
            side=Side.BUY,
            price=100,
            quantity=5,
        )
    )

    monitor = LatencyMonitor()
    monitor.record(10_000)

    state = LiveDashboardState(engine, monitor)
    snapshot = state.snapshot()

    assert snapshot["bids"] == [(100, 5)]
    assert snapshot["asks"] == []
    assert snapshot["latency"]["count"] == 1
    assert snapshot["last_trade"] is None
    assert snapshot["trades_per_s"] == 0


def test_record_trades_assigns_stable_sequential_ids():
    state = LiveDashboardState(MatchingEngine(), LatencyMonitor())

    trades = [
        Trade(
            buy_order_id=1,
            sell_order_id=2,
            price=100,
            quantity=3,
        ),
        Trade(
            buy_order_id=1,
            sell_order_id=3,
            price=100,
            quantity=2,
        ),
    ]

    state.record_trades(trades, levels_cleared=1)
    snapshot = state.snapshot()

    assert state.trade_count == 2
    assert snapshot["last_trade"] == {
        "trade_id": 2,
        "buy_order_id": 1,
        "sell_order_id": 3,
        "price_ticks": 100,
        "quantity": 2,
        "levels_cleared": 1,
    }
