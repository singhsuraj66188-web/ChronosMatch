"""Thread-safe live dashboard state for ChronosMatch."""
from __future__ import annotations

import threading
import time
from typing import Any

from chronosmatch.matching_engine import MatchingEngine
from monitoring.latency_monitor import LatencyMonitor


class LiveDashboardState:
    """Provide consistent dashboard snapshots while matching is running."""

    def __init__(
        self,
        engine: MatchingEngine,
        latency_monitor: LatencyMonitor,
    ) -> None:
        self.engine = engine
        self.latency_monitor = latency_monitor
        self.lock = threading.RLock()
        self.started_ns = time.perf_counter_ns()
        self.trade_count = 0
        self.last_trade: dict[str, Any] | None = None

    def record_trades(self, trades: list, levels_cleared: int) -> None:
        """Publish completed trades with stable, per-run dashboard IDs."""
        with self.lock:
            for trade in trades:
                self.trade_count += 1
                self.last_trade = {
                    "trade_id": self.trade_count,
                    "buy_order_id": trade.buy_order_id,
                    "sell_order_id": trade.sell_order_id,
                    "price_ticks": trade.price,
                    "quantity": trade.quantity,
                    "levels_cleared": levels_cleared,
                }

    def snapshot(self) -> dict[str, Any]:
        """Return a consistent snapshot in the dashboard's expected format."""
        with self.lock:
            elapsed_ns = max(
                time.perf_counter_ns() - self.started_ns,
                1,
            )
            trades_per_s = self.trade_count * 1_000_000_000 / elapsed_ns

            return {
                "bids": [
                    (order.price, order.quantity)
                    for order in self.engine.bids[:8]
                ],
                "asks": [
                    (order.price, order.quantity)
                    for order in self.engine.asks[:8]
                ],
                "latency": self.latency_monitor.summary(),
                "trades_per_s": trades_per_s,
                "last_trade": (
                    dict(self.last_trade)
                    if self.last_trade is not None
                    else None
                ),
            }
