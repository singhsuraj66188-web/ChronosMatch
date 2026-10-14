
"""Convert ring-buffer records into matching-engine orders."""

from __future__ import annotations

from collections.abc import Mapping

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side, Trade

_UINT64_MAX = (1 << 64) - 1
_UINT32_MAX = (1 << 32) - 1

_REQUIRED_FIELDS = (
    "sequence",
    "timestamp_ns",
    "price_ticks",
    "quantity",
    "side",
)


def order_from_record(record: Mapping[str, int]) -> Order:
    """Convert one ring-buffer record into a matching-engine order."""
    missing = [field for field in _REQUIRED_FIELDS if field not in record]

    if missing:
        raise ValueError(
            f"Missing ring-buffer fields: {', '.join(missing)}"
        )

    sequence = record["sequence"]
    timestamp_ns = record["timestamp_ns"]
    price_ticks = record["price_ticks"]
    quantity = record["quantity"]
    side_code = record["side"]

    if type(sequence) is not int or not 0 <= sequence <= _UINT64_MAX:
        raise ValueError("sequence must be an unsigned 64-bit integer")

    if (
        type(timestamp_ns) is not int
        or not 0 <= timestamp_ns <= _UINT64_MAX
    ):
        raise ValueError(
            "timestamp_ns must be an unsigned 64-bit integer"
        )

    if (
        type(price_ticks) is not int
        or not 1 <= price_ticks <= _UINT32_MAX
    ):
        raise ValueError(
            "price_ticks must be a positive unsigned 32-bit integer"
        )

    if (
        type(quantity) is not int
        or not 1 <= quantity <= _UINT32_MAX
    ):
        raise ValueError(
            "quantity must be a positive unsigned 32-bit integer"
        )

    if type(side_code) is not int or side_code not in (1, 2):
        raise ValueError("side must be 1 (BUY) or 2 (SELL)")

    side = Side.BUY if side_code == 1 else Side.SELL

    return Order(
        order_id=sequence + 1,
        side=side,
        price=price_ticks,
        quantity=quantity,
        timestamp=timestamp_ns,
    )


def process_record(
    record: Mapping[str, int],
    engine: MatchingEngine,
) -> list[Trade]:
    """Convert and submit one ring-buffer record to the engine."""
    order = order_from_record(record)
    return engine.submit_order(order)
