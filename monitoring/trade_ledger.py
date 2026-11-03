"""Asynchronous SQLite ledger for matched trades (Week 4: Resiliency).

The matching path only calls ``record()``, which puts a tuple on a queue.
A background thread batches rows and writes them to SQLite, so disk I/O
never blocks matching.

    with TradeLedger("trades.db") as ledger:
        ledger.record(price_ticks=10150, quantity=25, buy_order_id=7, sell_order_id=3)
        ledger.flush()              # optional: wait until everything is on disk
    print(TradeLedger.count("trades.db"))
"""
from __future__ import annotations

import queue
import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ns        INTEGER NOT NULL,
    buy_order_id  INTEGER,
    sell_order_id INTEGER,
    price_ticks  INTEGER NOT NULL,
    quantity     INTEGER NOT NULL
)
"""
_INSERT = (
    "INSERT INTO trades (ts_ns, buy_order_id, sell_order_id, price_ticks, quantity) "
    "VALUES (?, ?, ?, ?, ?)"
)
_STOP = object()


class _Flush:
    def __init__(self) -> None:
        self.done = threading.Event()


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


class TradeLedger:
    def __init__(self, path, batch_size: int = 500, flush_interval: float = 0.25) -> None:
        _require_positive_int("batch_size", batch_size)
        if not flush_interval > 0:
            raise ValueError("flush_interval must be positive")

        self._path = str(path)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._written = 0
        self._error: BaseException | None = None
        self._closed = False

        # Create the schema here so problems show up immediately.
        conn = sqlite3.connect(self._path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

        self._thread = threading.Thread(target=self._run, name="trade-ledger", daemon=True)
        self._thread.start()

    # ---- public API -------------------------------------------------
    @property
    def written(self) -> int:
        """Rows committed to disk so far."""
        return self._written

    def record(
        self,
        price_ticks: int,
        quantity: int,
        buy_order_id: int | None = None,
        sell_order_id: int | None = None,
        ts_ns: int | None = None,
    ) -> None:
        if self._closed:
            raise RuntimeError("ledger is closed")
        if self._error is not None:
            raise RuntimeError(f"ledger writer failed: {self._error!r}")
        _require_positive_int("price_ticks", price_ticks)
        _require_positive_int("quantity", quantity)
        if ts_ns is None:
            ts_ns = time.time_ns()
        self._queue.put((ts_ns, buy_order_id, sell_order_id, price_ticks, quantity))

    def flush(self, timeout: float = 30.0) -> None:
        """Block until every trade recorded so far is committed."""
        marker = _Flush()
        self._queue.put(marker)
        if not marker.done.wait(timeout):
            raise TimeoutError("ledger flush timed out")
        if self._error is not None:
            raise RuntimeError(f"ledger writer failed: {self._error!r}")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put(_STOP)
        self._thread.join(timeout=30)
        if self._error is not None:
            raise RuntimeError(f"ledger writer failed: {self._error!r}")

    def __enter__(self) -> "TradeLedger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def count(path) -> int:
        conn = sqlite3.connect(str(path))
        try:
            return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        finally:
            conn.close()

    # ---- writer thread ----------------------------------------------
    def _commit(self, conn: sqlite3.Connection, batch: list) -> None:
        if not batch:
            return
        conn.executemany(_INSERT, batch)
        conn.commit()
        self._written += len(batch)

    def _run(self) -> None:
        try:
            conn = sqlite3.connect(self._path)
            conn.execute("PRAGMA synchronous=NORMAL")
            batch: list = []
            last_commit = time.monotonic()
            while True:
                try:
                    item = self._queue.get(timeout=self._flush_interval)
                except queue.Empty:
                    item = None

                if isinstance(item, _Flush):
                    self._commit(conn, batch)
                    batch = []
                    last_commit = time.monotonic()
                    item.done.set()
                    continue

                stop = item is _STOP
                if item is not None and not stop:
                    batch.append(item)

                due = time.monotonic() - last_commit >= self._flush_interval
                if stop or len(batch) >= self._batch_size or (batch and due):
                    self._commit(conn, batch)
                    batch = []
                    last_commit = time.monotonic()
                if stop:
                    break
            conn.close()
        except BaseException as exc:  # surfaced via flush()/close()/record()
            self._error = exc