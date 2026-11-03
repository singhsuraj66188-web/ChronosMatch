from monitoring.curses_dashboard import detect_whale, render_lines


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