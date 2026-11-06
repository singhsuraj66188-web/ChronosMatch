
from web_dashboard.session_manager import SessionManager


def make_cookie(session_id):
    return f"chronosmatch_session={session_id}"


def test_new_visitors_receive_independent_exchanges():
    manager = SessionManager()

    exchange_a, session_a, is_new_a = manager.get_exchange()
    exchange_b, session_b, is_new_b = manager.get_exchange()

    assert is_new_a is True
    assert is_new_b is True
    assert session_a != session_b
    assert exchange_a is not exchange_b

    assert (
        exchange_a.get_account_snapshot()
        == exchange_b.get_account_snapshot()
    )


def test_same_session_reuses_its_exchange():
    manager = SessionManager()

    exchange_a, session_a, is_new = manager.get_exchange()

    cookie = make_cookie(session_a)
    exchange_again, same_session_id, is_new_again = (
        manager.get_exchange(cookie)
    )

    assert is_new is True
    assert is_new_again is False
    assert same_session_id == session_a
    assert exchange_again is exchange_a


def test_orders_are_not_shared_between_visitors():
    manager = SessionManager()

    exchange_a, _, _ = manager.get_exchange()
    exchange_b, _, _ = manager.get_exchange()

    result = exchange_a.submit_limit_order(
        symbol="BTC-SIM",
        side="BUY",
        price=6_499_500,
        quantity=1,
    )

    assert result["remaining_quantity"] == 1
    assert len(exchange_a.get_open_orders()) == 1
    assert exchange_b.get_open_orders() == []


def test_visitor_cannot_cancel_another_visitors_order():
    manager = SessionManager()

    exchange_a, _, _ = manager.get_exchange()
    exchange_b, _, _ = manager.get_exchange()

    result = exchange_a.submit_limit_order(
        symbol="BTC-SIM",
        side="BUY",
        price=6_499_500,
        quantity=1,
    )

    order_id = result["order_id"]

    try:
        exchange_b.cancel_order(order_id)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "A different visitor cancelled another visitor's order."
        )

    assert len(exchange_a.get_open_orders()) == 1
    assert exchange_b.get_open_orders() == []


def test_expired_session_gets_a_new_exchange(monkeypatch):
    import web_dashboard.session_manager as session_module

    current_time = [100.0]
    monkeypatch.setattr(
        session_module.time,
        "monotonic",
        lambda: current_time[0],
    )

    manager = SessionManager(session_ttl_seconds=60)

    original_exchange, session_id, _ = manager.get_exchange()

    current_time[0] = 161.0

    new_exchange, new_session_id, is_new = manager.get_exchange(
        make_cookie(session_id)
    )

    assert is_new is True
    assert new_session_id != session_id
    assert new_exchange is not original_exchange


def test_session_capacity_is_enforced():
    manager = SessionManager(max_sessions=1)

    manager.get_exchange()

    try:
        manager.get_exchange()
    except RuntimeError as error:
        assert "session capacity" in str(error)
    else:
        raise AssertionError(
            "SessionManager accepted a visitor beyond its capacity."
        )