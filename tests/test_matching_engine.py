from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side


def test_buy_matches_resting_sell_at_resting_price():
    engine = MatchingEngine()

    engine.submit_order(
        Order(order_id=1, side=Side.SELL, price=10000, quantity=5, timestamp=1)
    )

    trades = engine.submit_order(
        Order(order_id=2, side=Side.BUY, price=10100, quantity=3, timestamp=2)
    )

    assert len(trades) == 1
    assert trades[0].price == 10000
    assert trades[0].quantity == 3
    assert engine.asks[0].quantity == 2


def test_non_crossing_orders_do_not_trade():
    engine = MatchingEngine()

    engine.submit_order(
        Order(order_id=1, side=Side.SELL, price=10500, quantity=2)
    )

    trades = engine.submit_order(
        Order(order_id=2, side=Side.BUY, price=10000, quantity=2)
    )

    assert trades == []
    assert len(engine.asks) == 1
    assert len(engine.bids) == 1


def test_sell_matches_resting_buy_at_resting_price():
    engine = MatchingEngine()

    engine.submit_order(
        Order(order_id=1, side=Side.BUY, price=10000, quantity=4, timestamp=1)
    )

    trades = engine.submit_order(
        Order(order_id=2, side=Side.SELL, price=9900, quantity=2, timestamp=2)
    )

    assert len(trades) == 1
    assert trades[0].price == 10000
    assert trades[0].quantity == 2
    assert engine.bids[0].quantity == 2
import pytest


def test_best_price_order_matches_first():
    engine = MatchingEngine()

    engine.submit_order(
        Order(order_id=1, side=Side.SELL, price=10200, quantity=2, timestamp=1)
    )
    engine.submit_order(
        Order(order_id=2, side=Side.SELL, price=10100, quantity=2, timestamp=2)
    )

    trades = engine.submit_order(
        Order(order_id=3, side=Side.BUY, price=10300, quantity=1, timestamp=3)
    )

    assert len(trades) == 1
    assert trades[0].sell_order_id == 2
    assert trades[0].price == 10100


def test_order_matches_multiple_resting_orders():
    engine = MatchingEngine()

    engine.submit_order(
        Order(order_id=1, side=Side.SELL, price=10000, quantity=2, timestamp=1)
    )
    engine.submit_order(
        Order(order_id=2, side=Side.SELL, price=10000, quantity=3, timestamp=2)
    )

    trades = engine.submit_order(
        Order(order_id=3, side=Side.BUY, price=10000, quantity=4, timestamp=3)
    )

    assert [trade.quantity for trade in trades] == [2, 2]
    assert [trade.sell_order_id for trade in trades] == [1, 2]
    assert len(engine.asks) == 1
    assert engine.asks[0].order_id == 2
    assert engine.asks[0].quantity == 1


def test_duplicate_active_order_id_is_rejected():
    engine = MatchingEngine()

    engine.submit_order(
        Order(order_id=1, side=Side.BUY, price=10000, quantity=2)
    )

    with pytest.raises(ValueError, match="Duplicate active order ID"):
        engine.submit_order(
            Order(order_id=1, side=Side.SELL, price=10000, quantity=1)
        )

def test_same_price_orders_follow_timestamp_priority():
    engine = MatchingEngine()

    # Submit the later order first.
    engine.submit_order(
        Order(order_id=20, side=Side.SELL, price=10000, quantity=1, timestamp=2)
    )
    engine.submit_order(
        Order(order_id=10, side=Side.SELL, price=10000, quantity=1, timestamp=1)
    )

    trades = engine.submit_order(
        Order(order_id=30, side=Side.BUY, price=10000, quantity=1, timestamp=3)
    )

    assert len(trades) == 1
    assert trades[0].sell_order_id == 10


def test_same_price_and_timestamp_use_order_id_as_tiebreaker():
    engine = MatchingEngine()

    # Submit the higher ID first, with identical price and timestamp.
    engine.submit_order(
        Order(order_id=20, side=Side.SELL, price=10000, quantity=1, timestamp=5)
    )
    engine.submit_order(
        Order(order_id=10, side=Side.SELL, price=10000, quantity=1, timestamp=5)
    )

    trades = engine.submit_order(
        Order(order_id=30, side=Side.BUY, price=10000, quantity=1, timestamp=6)
    )

    assert len(trades) == 1
    assert trades[0].sell_order_id == 10
