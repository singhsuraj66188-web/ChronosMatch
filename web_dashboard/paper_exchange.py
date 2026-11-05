
from __future__ import annotations

import threading
import time

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, Side


class PaperExchange:
    """Synthetic-only paper exchange with independent matching engines."""

    INITIAL_BALANCE = 100_000_000

    MARKETS = {
        "BTC-SIM": 6_500_000,
        "ETH-SIM": 350_000,
        "SOL-SIM": 15_000,
    }

    def __init__(self):
        self.lock = threading.RLock()

        self.engines = {
            symbol: MatchingEngine() for symbol in self.MARKETS
        }

        self.next_order_id = 1
        self.cash_balance = self.INITIAL_BALANCE
        self.reserved_cash = 0

        self.positions = {symbol: 0 for symbol in self.MARKETS}
        self.reserved_positions = {symbol: 0 for symbol in self.MARKETS}

        self.open_orders = {}
        self.order_records = {}
        self.trades = []
        self.last_prices = dict(self.MARKETS)

        self._seed_order_books()

    def _new_order_id(self):
        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    def _seed_order_books(self):
        """Add synthetic liquidity to each independent market."""

        for symbol, price in self.MARKETS.items():
            engine = self.engines[symbol]

            for level in range(1, 6):
                for side, order_price in (
                    (Side.BUY, price - level * 100),
                    (Side.SELL, price + level * 100),
                ):
                    order_id = self._new_order_id()
                    quantity = 10 + level * 2

                    order = Order(
                        order_id=order_id,
                        side=side,
                        price=order_price,
                        quantity=quantity,
                        timestamp=level,
                    )

                    engine.submit_order(order)

                    self.order_records[order_id] = {
                        "order_id": order_id,
                        "symbol": symbol,
                        "side": side,
                        "price": order_price,
                        "remaining_quantity": quantity,
                        "owner": "synthetic",
                    }

    def _available_cash(self):
        return self.cash_balance - self.reserved_cash

    def _available_position(self, symbol):
        return (
            self.positions[symbol]
            - self.reserved_positions[symbol]
        )

    def get_account_snapshot(self):
        with self.lock:
            return {
                "initial_balance": self.INITIAL_BALANCE,
                "cash_balance": self.cash_balance,
                "reserved_cash": self.reserved_cash,
                "available_cash": self._available_cash(),
                "positions": dict(self.positions),
                "reserved_positions": dict(self.reserved_positions),
                "available_positions": {
                    symbol: self._available_position(symbol)
                    for symbol in self.MARKETS
                },
            }

    def get_market_snapshot(self, symbol):
        with self.lock:
            if symbol not in self.engines:
                raise ValueError(f"Unknown market: {symbol}")

            engine = self.engines[symbol]

            return {
                "symbol": symbol,
                "last_price": self.last_prices[symbol],
                "bids": [
                    {
                        "price": order.price,
                        "quantity": order.quantity,
                    }
                    for order in engine.bids[:10]
                ],
                "asks": [
                    {
                        "price": order.price,
                        "quantity": order.quantity,
                    }
                    for order in engine.asks[:10]
                ],
            }

    def get_open_orders(self):
        with self.lock:
            return [
                dict(order)
                for order in self.open_orders.values()
            ]

    def get_recent_trades(self, limit=50):
        with self.lock:
            return [
                dict(trade)
                for trade in self.trades[-limit:]
            ][::-1]

    def _check_self_trade(self, symbol, side, price):
        """Prevent an account order from matching its own resting order."""

        engine = self.engines[symbol]

        if side == Side.BUY:
            opposite_book = engine.asks
            crosses = lambda resting: price >= resting.price
        else:
            opposite_book = engine.bids
            crosses = lambda resting: price <= resting.price

        for resting in opposite_book:
            if not crosses(resting):
                break

            record = self.order_records.get(resting.order_id)

            if record and record["owner"] == "user":
                raise ValueError(
                    "Order would match your own resting order. "
                    "Cancel or change that order first."
                )

    def _settle_fill(self, fill, symbol):
        """Settle both buyer and seller sides of a matching-engine fill."""

        buyer = self.order_records.get(fill.buy_order_id)
        seller = self.order_records.get(fill.sell_order_id)

        if buyer is None or seller is None:
            raise RuntimeError("Order tracking record missing for a fill.")

        quantity = fill.quantity
        execution_value = fill.price * quantity

        # Release the buyer's reserved funds and settle the purchase.
        if buyer["owner"] == "user":
            reserved_value = buyer["price"] * quantity

            self.reserved_cash -= reserved_value
            self.cash_balance -= execution_value
            self.positions[symbol] += quantity

        # Release the seller's reserved holdings and settle the sale.
        if seller["owner"] == "user":
            self.reserved_positions[symbol] -= quantity
            self.cash_balance += execution_value
            self.positions[symbol] -= quantity

        buyer["remaining_quantity"] -= quantity
        seller["remaining_quantity"] -= quantity

        self.last_prices[symbol] = fill.price

        self.trades.append({
            "symbol": symbol,
            "buy_order_id": fill.buy_order_id,
            "sell_order_id": fill.sell_order_id,
            "price": fill.price,
            "quantity": quantity,
            "timestamp": time.time_ns(),
        })

        # Update or remove the buyer's open-order record.
        for record in (buyer, seller):
            order_id = record["order_id"]

            if record["owner"] != "user":
                continue

            if record["remaining_quantity"] > 0:
                self.open_orders[order_id] = {
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": record["side"].value,
                    "price": record["price"],
                    "quantity": record["remaining_quantity"],
                }
            else:
                self.open_orders.pop(order_id, None)

    def cancel_order(self, order_id):
        """Cancel a user's unfilled limit order and release its reservation."""

        with self.lock:
            if isinstance(order_id, bool):
                raise ValueError("Invalid order ID.")

            try:
                order_id = int(order_id)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Invalid order ID.") from None

            if order_id not in self.open_orders:
                raise ValueError("Open order not found or already completed.")

            record = self.order_records.get(order_id)

            if record is None or record["owner"] != "user":
                raise ValueError("Only your own open orders can be cancelled.")

            symbol = record["symbol"]
            side = record["side"]
            engine = self.engines[symbol]

            book = engine.bids if side == Side.BUY else engine.asks

            resting_order = next(
                (order for order in book if order.order_id == order_id),
                None,
            )

            if resting_order is None:
                raise RuntimeError(
                    "Order tracking is inconsistent with the market book."
                )

            remaining = record["remaining_quantity"]

            if remaining <= 0 or resting_order.quantity != remaining:
                raise RuntimeError("Order quantity tracking is inconsistent.")

            # Remove the order from the market book and active-order index.
            book.remove(resting_order)
            engine.active_order_ids.remove(order_id)

            # Release only the unfilled reservation.
            if side == Side.BUY:
                self.reserved_cash -= record["price"] * remaining
            else:
                self.reserved_positions[symbol] -= remaining

            self.open_orders.pop(order_id)

            record["status"] = "cancelled"
            record["cancelled_quantity"] = remaining
            record["remaining_quantity"] = 0

            return {
                "order_id": order_id,
                "symbol": symbol,
                "side": side.value,
                "price": record["price"],
                "cancelled_quantity": remaining,
                "status": "cancelled",
            }

    def submit_limit_order(self, symbol, side, price, quantity):
        with self.lock:
            if symbol not in self.engines:
                raise ValueError(f"Unknown market: {symbol}")

            try:
                side = Side(side.upper())
            except (AttributeError, ValueError):
                raise ValueError("Side must be BUY or SELL.") from None

            if isinstance(price, bool) or isinstance(quantity, bool):
                raise ValueError(
                    "Price and quantity must be whole numbers."
                )

            if (
                isinstance(price, float) and not price.is_integer()
            ) or (
                isinstance(quantity, float) and not quantity.is_integer()
            ):
                raise ValueError(
                    "Price and quantity must be whole numbers."
                )

            try:
                price = int(price)
                quantity = int(quantity)
            except (TypeError, ValueError, OverflowError):
                raise ValueError(
                    "Price and quantity must be whole numbers."
                ) from None

            if price <= 0 or quantity <= 0:
                raise ValueError(
                    "Price and quantity must be positive."
                )

            # Prevent orders from trading against the same account.
            self._check_self_trade(symbol, side, price)

            # Reserve funds or holdings before submitting the order.
            if side == Side.BUY:
                required_cash = price * quantity

                if required_cash > self._available_cash():
                    raise ValueError(
                        "Insufficient available virtual cash."
                    )

                self.reserved_cash += required_cash

            else:
                if quantity > self._available_position(symbol):
                    raise ValueError(
                        "Insufficient available virtual holdings."
                    )

                self.reserved_positions[symbol] += quantity

            order_id = self._new_order_id()

            order = Order(
                order_id=order_id,
                side=side,
                price=price,
                quantity=quantity,
                timestamp=time.time_ns(),
            )

            self.order_records[order_id] = {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "price": price,
                "remaining_quantity": quantity,
                "owner": "user",
            }

            original_quantity = quantity

            try:
                fills = self.engines[symbol].submit_order(order)

                for fill in fills:
                    self._settle_fill(fill, symbol)

            except Exception:
                # Do not leave funds reserved if submission fails.
                record = self.order_records.pop(order_id, None)

                if record:
                    remaining = record["remaining_quantity"]

                    if side == Side.BUY:
                        self.reserved_cash -= price * remaining
                    else:
                        self.reserved_positions[symbol] -= remaining

                self.open_orders.pop(order_id, None)
                raise

            record = self.order_records[order_id]
            filled_quantity = original_quantity - record["remaining_quantity"]
            remaining_quantity = record["remaining_quantity"]

            if remaining_quantity > 0:
                self.open_orders[order_id] = {
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side.value,
                    "price": price,
                    "quantity": remaining_quantity,
                }

            return {
                "order_id": order_id,
                "symbol": symbol,
                "side": side.value,
                "requested_quantity": original_quantity,
                "filled_quantity": filled_quantity,
                "remaining_quantity": remaining_quantity,
                "trades": [
                    {
                        "price": fill.price,
                        "quantity": fill.quantity,
                    }
                    for fill in fills
                ],
            }
