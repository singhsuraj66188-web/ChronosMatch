from monitoring.curses_dashboard import (
    WhaleAlertTracker,
    detect_whale,
    render_lines,
    whale_alert_message,
)


def _snap(**over):
    snap = {
        "bids": [(100, 10), (99, 20)],
        "asks": [(102, 5), (103, 7)],
        "latency": {"median_us": 12.0, "p99_us": 40.0, "max_us": 90.0, "count": 1000},
        "trades_per_s": 45_000.0,
        "last_trade": None,
    }
    snap.update(over)
    return snap


def _text(lines):
    return "\n".join(t for t, _ in lines)


def test_shows_spread_and_latency():
    text = _text(render_lines(_snap()))
    assert "best bid 100" in text and "best ask 102" in text and "spread 2" in text
    assert "p99 40.0 us" in text
    assert "45,000 trades/s" in text


def test_empty_book_does_not_crash():
    text = _text(render_lines({"bids": [], "asks": []}))
    assert "spread -" in text


def test_lines_are_truncated_to_width():
    assert all(len(t) <= 29 for t, _ in render_lines(_snap(), width=30))


def test_whale_banner_only_when_active():
    assert "WHALE" not in _text(render_lines(_snap()))
    lines = render_lines(_snap(), whale_active=True)
    assert any(style == "whale" and "WHALE" in t for t, style in lines)


def test_detect_whale():
    assert not detect_whale(None)
    assert not detect_whale({"quantity": 10, "levels_cleared": 1})
    assert detect_whale({"quantity": 900, "levels_cleared": 1})
    assert detect_whale({"quantity": 10, "levels_cleared": 4})


def test_tracker_does_not_retrigger_for_fresh_dicts_with_same_trade_id():
    tracker = WhaleAlertTracker()
    assert tracker.observe({"trade_id": 42, "quantity": 900, "levels_cleared": 1})
    assert not tracker.observe({"trade_id": 42, "quantity": 900, "levels_cleared": 1})


def test_tracker_detects_new_trade_when_same_dict_is_mutated():
    tracker = WhaleAlertTracker()
    trade = {"trade_id": 42, "quantity": 900, "levels_cleared": 1}
    assert tracker.observe(trade)
    trade["trade_id"] = 43
    assert tracker.observe(trade)


def test_tracker_requires_stable_identifier():
    import pytest

    tracker = WhaleAlertTracker()
    with pytest.raises(ValueError, match="stable trade_id or sequence"):
        tracker.observe({"quantity": 900})


def test_whale_alert_message_matches_quantity_only_trigger():
    message = whale_alert_message({"quantity": 900, "levels_cleared": 1})
    assert "large quantity" in message
    assert "multi-level sweep" not in message


def test_whale_alert_message_matches_sweep_only_trigger():
    message = whale_alert_message({"quantity": 10, "levels_cleared": 4})
    assert "multi-level sweep" in message
    assert "large quantity" not in message


def test_whale_alert_message_describes_both_triggers():
    message = whale_alert_message({"quantity": 900, "levels_cleared": 4})
    assert "large quantity + multi-level sweep" in message


def test_active_banner_keeps_original_trigger_reason():
    lines = render_lines(
        _snap(last_trade={"trade_id": 2, "quantity": 10, "levels_cleared": 1}),
        whale_active=True,
        whale_message="*** WHALE ORDER: large quantity ***",
    )
    assert "*** WHALE ORDER: large quantity ***" in _text(lines)
