import sqlite3
import threading

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


def test_flush_surfaces_writer_failure_without_waiting_for_timeout(tmp_path, monkeypatch):
    ledger = TradeLedger(tmp_path / "failed.db", flush_interval=10)

    def fail_commit(conn, batch):
        raise sqlite3.OperationalError("simulated disk write failure")

    monkeypatch.setattr(ledger, "_commit", fail_commit)
    ledger.record(price_ticks=101, quantity=2)
    with pytest.raises(RuntimeError, match="ledger writer failed"):
        ledger.flush(timeout=1)
    with pytest.raises(RuntimeError, match="ledger writer failed"):
        ledger.close()


def test_close_reports_writer_thread_timeout(tmp_path, monkeypatch):
    ledger = TradeLedger(tmp_path / "slow.db", batch_size=1)
    entered_commit = threading.Event()
    release_commit = threading.Event()
    real_join = ledger._thread.join

    def blocked_commit(conn, batch):
        entered_commit.set()
        release_commit.wait(timeout=3)

    monkeypatch.setattr(ledger, "_commit", blocked_commit)
    monkeypatch.setattr(ledger._thread, "join", lambda timeout=None: None)
    try:
        ledger.record(price_ticks=101, quantity=2)
        assert entered_commit.wait(timeout=1)
        with pytest.raises(TimeoutError, match="writer thread did not stop"):
            ledger.close()
    finally:
        release_commit.set()
        real_join(timeout=2)
    assert not ledger._thread.is_alive()
