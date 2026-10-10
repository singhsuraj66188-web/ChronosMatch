from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    order_id: int
    side: Side
    price: int
    quantity: int
    timestamp: int = 0

    def __post_init__(self) -> None:
        if self.order_id < 1:
            raise ValueError("order_id must be positive")
        if self.price < 1:
            raise ValueError("price must be positive")
        if self.quantity < 1:
            raise ValueError("quantity must be positive")
        if not isinstance(self.side, Side):
            raise ValueError("side must be Side.BUY or Side.SELL")


@dataclass(frozen=True)
class Trade:
    buy_order_id: int
    sell_order_id: int
    price: int
    quantity: int