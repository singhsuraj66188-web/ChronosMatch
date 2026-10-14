
import pytest

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Side
from ipc.matching_consumer import order_from_record, process_record
from ipc.ring_buffer import RingBuffer


def test_buy_record_maps_to_matching_engine_order():
    record = {
        "sequence": 0,
        "timestamp_ns": 123,
        "price_ticks": 10000,
        "quantity": 2,
        "side": 1,
    }

    order = order_from_record(record)

    assert order.order_id == 1
    assert order.side == Side.BUY
    assert order.price == 10000
    assert order.quantity == 2
    assert order.timestamp == 123


def test_ring_buffer_record_enters_bid_book(tmp_path):
    engine = MatchingEngine()
    path = tmp_path / "matching.bin"

    with RingBuffer(path, capacity=4, create=True) as ring:
        assert ring.write(
            timestamp_ns=123,
            price_ticks=10000,
            quantity=2,
            side=1,
        )

        record = ring.read()
        assert record is not None

        trades = process_record(record, engine)
        assert trades == []

    assert len(engine.bids) == 1
    assert engine.bids[0].order_id == 1
    assert engine.bids[0].side == Side.BUY
    assert engine.bids[0].price == 10000
    assert engine.bids[0].quantity == 2


def test_crossing_records_create_trade(tmp_path):
    engine = MatchingEngine()
    path = tmp_path / "matching.bin"

    with RingBuffer(path, capacity=4, create=True) as ring:
        assert ring.write(
            timestamp_ns=100,
            price_ticks=10000,
            quantity=2,
            side=2,
        )

        sell_record = ring.read()
        assert sell_record is not None
        assert process_record(sell_record, engine) == []

        assert ring.write(
            timestamp_ns=200,
            price_ticks=10100,
            quantity=1,
            side=1,
        )

        buy_record = ring.read()
        assert buy_record is not None
        trades = process_record(buy_record, engine)

    assert len(trades) == 1
    assert trades[0].buy_order_id == 2
    assert trades[0].sell_order_id == 1
    assert trades[0].price == 10000
    assert trades[0].quantity == 1

    assert len(engine.asks) == 1
    assert engine.asks[0].quantity == 1


def test_invalid_side_is_rejected():
    record = {
        "sequence": 0,
        "timestamp_ns": 123,
        "price_ticks": 10000,
        "quantity": 2,
        "side": 3,
    }

    with pytest.raises(ValueError, match="side must be"):
        order_from_record(record)


def test_missing_record_field_is_rejected():
    record = {
        "sequence": 0,
        "timestamp_ns": 123,
        "price_ticks": 10000,
        "quantity": 2,
    }

    with pytest.raises(ValueError, match="Missing ring-buffer fields"):
        order_from_record(record)
