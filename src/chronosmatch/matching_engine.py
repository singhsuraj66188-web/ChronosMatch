from bisect import bisect_right

from chronosmatch.order import Order, Side, Trade


class MatchingEngine:
    """Reference matching engine with price-time-sorted order books."""

    def __init__(self) -> None:
        self.bids: list[Order] = []
        self.asks: list[Order] = []
        self.active_order_ids: set[int] = set()

    @staticmethod
    def _bid_key(order: Order) -> tuple[int, int, int]:
        # Higher bid price first, then earlier timestamp and order ID.
        return (-order.price, order.timestamp, order.order_id)

    @staticmethod
    def _ask_key(order: Order) -> tuple[int, int, int]:
        # Lower ask price first, then earlier timestamp and order ID.
        return (order.price, order.timestamp, order.order_id)

    def _insert_order(self, book: list[Order], order: Order) -> None:
        if order.side == Side.BUY:
            index = bisect_right(book, self._bid_key(order), key=self._bid_key)
        else:
            index = bisect_right(book, self._ask_key(order), key=self._ask_key)

        book.insert(index, order)

    def submit_order(self, order: Order) -> list[Trade]:
        if order.order_id in self.active_order_ids:
            raise ValueError(f"Duplicate active order ID: {order.order_id}")

        self.active_order_ids.add(order.order_id)
        incoming_quantity = order.quantity
        trades: list[Trade] = []

        if order.side == Side.BUY:
            opposite_book = self.asks
            crosses = lambda resting: order.price >= resting.price
        else:
            opposite_book = self.bids
            crosses = lambda resting: order.price <= resting.price

        # The opposite book is already sorted, so no full-book sort is needed.
        while incoming_quantity > 0 and opposite_book:
            resting = opposite_book[0]

            if not crosses(resting):
                break

            traded_quantity = min(incoming_quantity, resting.quantity)

            if order.side == Side.BUY:
                buy_order_id = order.order_id
                sell_order_id = resting.order_id
            else:
                buy_order_id = resting.order_id
                sell_order_id = order.order_id

            trades.append(
                Trade(
                    buy_order_id=buy_order_id,
                    sell_order_id=sell_order_id,
                    price=resting.price,
                    quantity=traded_quantity,
                )
            )

            incoming_quantity -= traded_quantity
            resting.quantity -= traded_quantity

            if resting.quantity == 0:
                opposite_book.pop(0)
                self.active_order_ids.remove(resting.order_id)

        if incoming_quantity > 0:
            order.quantity = incoming_quantity

            if order.side == Side.BUY:
                self._insert_order(self.bids, order)
            else:
                self._insert_order(self.asks, order)
        else:
            self.active_order_ids.remove(order.order_id)

        return trades