"""Live terminal dashboard: top of book, spread, latency, and a whale alert.

Every non-None last_trade must include a stable trade_id (or sequence), so
repeated snapshots of the same trade do not retrigger alerts.
"""
from __future__ import annotations

import argparse
import random
import time

try:
    import curses
except ImportError:
    curses = None

DEPTH = 8
WHALE_QTY = 500
WHALE_LEVELS = 3
WHALE_SHOW_SECONDS = 3.0


def detect_whale(trade: dict | None, qty_threshold: int = WHALE_QTY,
                 levels_threshold: int = WHALE_LEVELS) -> bool:
    """A whale is a large trade, a multi-level sweep, or both."""
    if not trade:
        return False
    return (
        trade.get("quantity", 0) >= qty_threshold
        or trade.get("levels_cleared", 0) >= levels_threshold
    )


def _trade_identity(trade: dict | None):
    """Return the stable identity required to recognize a newly observed trade."""
    if trade is None:
        return None
    identity = trade.get("trade_id", trade.get("sequence"))
    if identity is None:
        raise ValueError("last_trade must include a stable trade_id or sequence")
    return identity


class WhaleAlertTracker:
    """Track stable trade IDs rather than snapshot-dictionary object identity."""

    def __init__(self) -> None:
        self._last_trade_id = None

    def observe(self, trade: dict | None) -> bool:
        trade_id = _trade_identity(trade)
        is_new = trade_id is not None and trade_id != self._last_trade_id
        self._last_trade_id = trade_id
        return bool(is_new and detect_whale(trade))


def whale_alert_message(trade: dict | None) -> str:
    """Describe the actual condition that caused a whale alert."""
    if trade is None:
        return "*** WHALE ORDER ***"
    large = trade.get("quantity", 0) >= WHALE_QTY
    sweep = trade.get("levels_cleared", 0) >= WHALE_LEVELS
    if large and sweep:
        reason = "large quantity + multi-level sweep"
    elif large:
        reason = "large quantity"
    else:
        reason = "multi-level sweep"
    return f"*** WHALE ORDER: {reason} ***"


def render_lines(snapshot: dict, width: int = 80, whale_active: bool = False,
                 whale_message: str | None = None):
    """Return [(text, style)] lines. Pure function, so it is easy to test."""
    bids = list(snapshot.get("bids") or [])
    asks = list(snapshot.get("asks") or [])
    lat = snapshot.get("latency") or {}
    lines: list[tuple[str, str]] = []

    lines.append(("ChronosMatch  |  live order book   (q to quit)", "title"))

    if bids and asks:
        spread = asks[0][0] - bids[0][0]
        lines.append(
            (f"best bid {bids[0][0]}   best ask {asks[0][0]}   spread {spread}", "spread")
        )
    else:
        lines.append(("best bid -   best ask -   spread -", "spread"))

    lines.append((f"{'BID qty':>10} {'price':>10}  |  {'price':<10} {'ASK qty':<10}", "header"))
    for i in range(DEPTH):
        b = f"{bids[i][1]:>10} {bids[i][0]:>10}" if i < len(bids) else " " * 21
        a = f"{asks[i][0]:<10} {asks[i][1]:<10}" if i < len(asks) else ""
        lines.append((f"{b}  |  {a}", "book"))

    lines.append(("", "dim"))
    lines.append(
        (
            "latency  p50 {:.1f} us   p99 {:.1f} us   max {:.1f} us   samples {}".format(
                lat.get("median_us", 0.0),
                lat.get("p99_us", 0.0),
                lat.get("max_us", 0.0),
                lat.get("count", 0),
            ),
            "latency",
        )
    )
    lines.append((f"throughput  {snapshot.get('trades_per_s', 0.0):,.0f} trades/s", "latency"))

    trade = snapshot.get("last_trade")
    if trade:
        lines.append(
            (
                f"last trade  {trade.get('quantity', 0)} @ {trade.get('price_ticks', 0)}"
                f"  (levels cleared: {trade.get('levels_cleared', 0)})",
                "dim",
            )
        )
    if whale_active:
        lines.append((whale_message or whale_alert_message(trade), "whale"))

    return [(text[: max(width - 1, 0)], style) for text, style in lines]


def run(snapshot_fn, refresh: float = 0.1) -> None:
    """Show the dashboard until the user presses q."""
    if curses is None:
        raise SystemExit("curses is missing. On Windows run: pip install windows-curses")

    def _main(stdscr):
        curses.curs_set(0)
        stdscr.nodelay(True)
        styles = {"normal": curses.A_NORMAL, "dim": curses.A_DIM, "title": curses.A_BOLD,
                  "header": curses.A_BOLD, "book": curses.A_NORMAL, "spread": curses.A_BOLD,
                  "latency": curses.A_NORMAL, "bid": curses.A_NORMAL, "ask": curses.A_NORMAL,
                  "whale": curses.A_REVERSE | curses.A_BOLD}
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_CYAN, -1)
            curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_RED)
            styles["book"] = curses.color_pair(3)
            styles["latency"] = curses.color_pair(1)
            styles["whale"] = curses.color_pair(4) | curses.A_BOLD

        whale_until = 0.0
        active_whale_message = None
        tracker = WhaleAlertTracker()
        while True:
            if stdscr.getch() in (ord("q"), ord("Q")):
                return
            snap = snapshot_fn()
            trade = snap.get("last_trade")
            if tracker.observe(trade):
                active_whale_message = whale_alert_message(trade)
                whale_until = time.monotonic() + WHALE_SHOW_SECONDS

            height, width = stdscr.getmaxyx()
            stdscr.erase()
            whale_active = time.monotonic() < whale_until
            lines = render_lines(
                snap, width, whale_active=whale_active,
                whale_message=active_whale_message,
            )
            for row, (line, style) in enumerate(lines[: max(height - 1, 0)]):
                try:
                    stdscr.addstr(row, 0, line, styles.get(style, curses.A_NORMAL))
                except curses.error:
                    pass
            stdscr.refresh()
            time.sleep(refresh)

    try:
        curses.wrapper(_main)
    except KeyboardInterrupt:
        pass


def _demo_snapshot_factory():
    mid = 10_000
    state = {"mid": mid, "n": 0, "last": None, "trade_id": 0}

    def snapshot() -> dict:
        state["n"] += 1
        state["mid"] += random.choice((-1, 0, 1))
        mid_ = state["mid"]
        bids = [(mid_ - 1 - i, random.randint(5, 200)) for i in range(DEPTH)]
        asks = [(mid_ + 1 + i, random.randint(5, 200)) for i in range(DEPTH)]
        if state["n"] % 50 == 0:
            state["trade_id"] += 1
            state["last"] = {"trade_id": state["trade_id"], "price_ticks": mid_ + 4,
                             "quantity": 900, "levels_cleared": 4}
        elif state["n"] % 7 == 0:
            state["trade_id"] += 1
            state["last"] = {"trade_id": state["trade_id"], "price_ticks": mid_,
                             "quantity": random.randint(1, 60), "levels_cleared": 1}
        return {
            "bids": bids,
            "asks": asks,
            "latency": {"median_us": random.uniform(8, 15), "p99_us": random.uniform(30, 60),
                        "max_us": random.uniform(70, 150), "count": state["n"] * 10},
            "trades_per_s": random.uniform(40_000, 46_000),
            "last_trade": state["last"],
        }

    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="show synthetic data")
    args = parser.parse_args()
    if not args.demo:
        raise SystemExit("Pass --demo, or call run(snapshot_fn) from your own code.")
    run(_demo_snapshot_factory())
