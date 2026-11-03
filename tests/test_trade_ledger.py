import sqlite3

import pytest

from monitoring.trade_ledger import TradeLedger


def test_records_are_written_in_order(tmp_path):
    db = tmp_path / "trades.db"
    with TradeLedger(db, batch_size=100, flush_interval=0.05) as ledger:
        for i in range(1, 1001):
            ledger.record(price_ticks=10_000 + i, quantity=i, buy_order_id=i, sell_order_id=i + 1)
        ledger.flush()
        assert ledger.written == 1000
    assert TradeLedger.count(db) == 1000
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT price_ticks FROM trades ORDER BY id").fetchall()
    finally:
        conn.close()
    assert [r[0] for r in rows] == [10_000 + i for i in range(1, 1001)]


def test_close_drains_pending_records(tmp_path):
    db = tmp_path / "trades.db"
    ledger = TradeLedger(db, batch_size=10_000, flush_interval=10)
    for i in range(1, 51):
        ledger.record(price_ticks=i, quantity=1)
    ledger.close()
    assert TradeLedger.count(db) == 50


def test_data_survives_reopening(tmp_path):
    db = tmp_path / "trades.db"
    with TradeLedger(db) as ledger:
        ledger.record(price_ticks=5, quantity=2)
    with TradeLedger(db) as ledger:
        ledger.record(price_ticks=6, quantity=3)
    assert TradeLedger.count(db) == 2


@pytest.mark.parametrize("price,qty", [(0, 1), (-1, 1), (1, 0), (1.5, 1), (True, 1), (1, "2")])
def test_rejects_invalid_trades(tmp_path, price, qty):
    with TradeLedger(tmp_path / "t.db") as ledger:
        with pytest.raises(ValueError):
            ledger.record(price_ticks=price, quantity=qty)


def test_record_after_close_raises(tmp_path):
    ledger = TradeLedger(tmp_path / "t.db")
    ledger.close()
    with pytest.raises(RuntimeError):
        ledger.record(price_ticks=1, quantity=1)


@pytest.mark.parametrize("kwargs", [{"batch_size": 0}, {"batch_size": True}, {"flush_interval": 0}])
def test_rejects_invalid_configuration(tmp_path, kwargs):
    with pytest.raises(ValueError):
        TradeLedger(tmp_path / "t.db", **kwargs)