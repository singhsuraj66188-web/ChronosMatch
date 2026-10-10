import pytest

from chronosmatch.order import Order, Side


@pytest.mark.parametrize(
    ("order_id", "side", "price", "quantity"),
    [
        (0, Side.BUY, 10000, 1),
        (1, Side.BUY, 0, 1),
        (1, Side.SELL, 10000, 0),
        (-1, Side.BUY, 10000, 1),
        (1, Side.SELL, -100, 1),
    ],
)
def test_invalid_orders_are_rejected(order_id, side, price, quantity):
    with pytest.raises(ValueError):
        Order(
            order_id=order_id,
            side=side,
            price=price,
            quantity=quantity,
        )


def test_valid_buy_order_is_created():
    order = Order(
        order_id=1,
        side=Side.BUY,
        price=10000,
        quantity=5,
        timestamp=10,
    )

    assert order.order_id == 1
    assert order.side == Side.BUY
    assert order.price == 10000
    assert order.quantity == 5
    assert order.timestamp == 10


def test_invalid_side_is_rejected():
    with pytest.raises(ValueError, match="side must be"):
        Order(
            order_id=1,
            side="INVALID",
            price=10000,
            quantity=1,
        )