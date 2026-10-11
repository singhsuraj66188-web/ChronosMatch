
from __future__ import annotations

import argparse
import asyncio
import math
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Tick:
    sequence: int
    timestamp_ns: int
    symbol: str
    price_ticks: int
    quantity: int
    side: int  # 1 = BUY, 2 = SELL


async def generate_ticks(
    count: int = 100,
    interval_ms: float = 10.0,
    seed: int = 7,
) -> AsyncIterator[Tick]:
    """Generate synthetic ticks for testing; no real exchange is used."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 0:
        raise ValueError("count cannot be negative")
    if not math.isfinite(interval_ms) or interval_ms < 0:
        raise ValueError("interval_ms must be finite and non-negative")

    rng = random.Random(seed)
    price = 10_000

    for sequence in range(count):
        price = max(1, price + rng.choice((-2, -1, 0, 1, 2)))

        yield Tick(
            sequence=sequence,
            timestamp_ns=time.perf_counter_ns(),
            symbol="SIM",
            price_ticks=price,
            quantity=rng.randint(1, 10),
            side=rng.choice((1, 2)),
        )

        if interval_ms:
            await asyncio.sleep(interval_ms / 1000)


async def run(count: int, interval_ms: float, seed: int) -> None:
    total = 0
    start = time.perf_counter()

    async for tick in generate_ticks(count, interval_ms, seed):
        total += 1
        side = "BUY" if tick.side == 1 else "SELL"

        print(
            f"seq={tick.sequence:05d} "
            f"symbol={tick.symbol} "
            f"price_ticks={tick.price_ticks} "
            f"qty={tick.quantity} side={side}"
        )

    elapsed = time.perf_counter() - start
    rate = total / elapsed if elapsed > 0 else 0.0

    print(f"Generated {total} simulated ticks in {elapsed:.3f}s")
    print(f"Approximate end-to-end simulator throughput: {rate:.1f} ticks/s")
    print("Note: This includes waiting and terminal output; it is not engine latency.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ChronosMatch simulated market-data generator"
    )
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--interval-ms", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=7)

    args = parser.parse_args()
    asyncio.run(run(args.count, args.interval_ms, args.seed))


if __name__ == "__main__":
    main()
