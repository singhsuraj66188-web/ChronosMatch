import pytest

from web_dashboard.paper_exchange import PaperExchange


def test_cancel_buy_order_releases_reserved_cash():
    exchange = PaperExchange()
    symbol = "BTC-SIM"

    result = exchange.submit_limit_order(
        symbol, "BUY", 6_499_000, 5
    )
    order_id = result["order_id"]

    assert exchange.reserved_cash == 6_499_000 * 5

    cancelled = exchange.cancel_order(order_id)

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_quantity"] == 5
    assert exchange.reserved_cash == 0
    assert exchange.get_open_orders() == []


def test_cancel_sell_order_releases_reserved_holdings():
    exchange = PaperExchange()
    symbol = "BTC-SIM"

    # Acquire virtual holdings by matching against a synthetic ask.
    exchange.submit_limit_order(
        symbol, "BUY", 6_500_100, 5
    )

    result = exchange.submit_limit_order(
        symbol, "SELL", 6_500_000, 2
    )
    order_id = result["order_id"]

    assert exchange.reserved_positions[symbol] == 2

    cancelled = exchange.cancel_order(order_id)

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_quantity"] == 2
    assert exchange.reserved_positions[symbol] == 0
    assert exchange.positions[symbol] == 5
    assert exchange.get_open_orders() == []


def test_cancel_partially_filled_buy_order_preserves_completed_fill():
    exchange = PaperExchange()
    symbol = "ETH-SIM"

    result = exchange.submit_limit_order(
        symbol, "BUY", 350_250, 30
    )
    order_id = result["order_id"]

    assert result["filled_quantity"] == 26
    assert result["remaining_quantity"] == 4
    assert exchange.positions[symbol] == 26

    cash_before_cancel = exchange.cash_balance
    trades_before_cancel = exchange.get_recent_trades()

    cancelled = exchange.cancel_order(order_id)

    assert cancelled["cancelled_quantity"] == 4
    assert exchange.positions[symbol] == 26
    assert exchange.cash_balance == cash_before_cancel
    assert exchange.get_recent_trades() == trades_before_cancel
    assert exchange.reserved_cash == 0
    assert exchange.get_open_orders() == []


def test_cancel_order_twice_is_rejected():
    exchange = PaperExchange()

    result = exchange.submit_limit_order(
        "BTC-SIM", "BUY", 6_499_000, 5
    )
    order_id = result["order_id"]

    exchange.cancel_order(order_id)

    with pytest.raises(ValueError, match="Open order not found"):
        exchange.cancel_order(order_id)
