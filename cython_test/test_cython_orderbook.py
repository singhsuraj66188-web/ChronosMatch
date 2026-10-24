import sys
from pathlib import Path

import pytest

# The extension module is built in the project root and is available when tests
# are run from the cython_test directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cython_orderbook import OrderBook  # pyright: ignore[reportMissingImports]


def test_partial_fill():
    book = OrderBook()
    assert book.add_order("SELL", 100, 10) == []
    assert book.add_order("BUY", 100, 6) == [(100, 6, "BUY")]
    assert book.add_order("BUY", 100, 8) == [(100, 4, "BUY")]


def test_price_priority_and_fifo():
    book = OrderBook()
    book.add_order("SELL", 105, 3)
    book.add_order("SELL", 100, 2)
    book.add_order("SELL", 100, 4)

    assert book.add_order("BUY", 105, 5) == [
        (100, 2, "BUY"),
        (100, 3, "BUY"),
    ]


@pytest.mark.parametrize(
    "side,price,quantity",
    [
        ("BUY", 0, 1),
        ("SELL", 100, 0),
        ("INVALID", 100, 1),
        ("BUY", -1, 1),
        ("SELL", 100, -1),
    ],
)
def test_invalid_orders_are_rejected(side, price, quantity):
    book = OrderBook()
    with pytest.raises(ValueError):
        book.add_order(side, price, quantity)
