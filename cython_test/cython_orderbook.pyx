
# cython_orderbook.pyx
# Minimal price-time-priority limit order book prototype.

from collections import deque


cdef class OrderBook:
    cdef dict bids
    cdef dict asks

    def __cinit__(self):
        self.bids = {}
        self.asks = {}

    cpdef list add_order(self, str side, long long price,
                         long long quantity):
        cdef dict opposite
        cdef dict own
        cdef list prices
        cdef object level
        cdef object resting
        cdef long long best_price
        cdef long long available
        cdef long long traded
        cdef list trades = []

        if price <= 0 or quantity <= 0:
            raise ValueError("Price and quantity must be positive")

        if side == "BUY":
            opposite = self.asks
            own = self.bids
        elif side == "SELL":
            opposite = self.bids
            own = self.asks
        else:
            raise ValueError("side must be BUY or SELL")

        while quantity > 0 and opposite:
            prices = list(opposite.keys())

            if side == "BUY":
                best_price = min(prices)
                if best_price > price:
                    break
            else:
                best_price = max(prices)
                if best_price < price:
                    break

            level = opposite[best_price]

            while quantity > 0 and level:
                resting = level[0]
                available = resting[1]
                traded = min(quantity, available)

                # Record execution price, quantity, incoming side.
                trades.append((best_price, traded, side))

                quantity -= traded
                available -= traded

                if available == 0:
                    level.popleft()
                else:
                    level[0] = (resting[0], available)

            if not level:
                del opposite[best_price]

        if quantity > 0:
            if price not in own:
                own[price] = deque()

            own[price].append((side, quantity))

        return trades
