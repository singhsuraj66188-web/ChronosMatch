
from __future__ import annotations

import math
import statistics
from collections import deque


class LatencyMonitor:
    """Collect nanosecond samples in a bounded rolling window."""

    def __init__(self, max_samples: int = 10_000) -> None:
        if isinstance(max_samples, bool) or not isinstance(max_samples, int):
            raise TypeError("max_samples must be an integer")
        if max_samples <= 0:
            raise ValueError("max_samples must be positive")

        self._samples_ns: deque[int] = deque(maxlen=max_samples)

    def record(self, duration_ns: int) -> None:
        if duration_ns < 0:
            raise ValueError("duration_ns cannot be negative")
        self._samples_ns.append(duration_ns)

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> int:
        """Return the nearest-rank percentile from sorted values."""
        if not values:
            return 0
        if not math.isfinite(percentile) or not 0 < percentile <= 100:
            raise ValueError("percentile must be greater than 0 and at most 100")

        index = math.ceil((percentile / 100) * len(values)) - 1
        return values[index]

    def summary(self) -> dict[str, float | int]:
        if not self._samples_ns:
            return {
                "count": 0,
                "median_us": 0.0,
                "p95_us": 0.0,
                "p99_us": 0.0,
            }

        ordered = sorted(self._samples_ns)

        return {
            "count": len(ordered),
            "median_us": statistics.median(ordered) / 1000,
            "p95_us": self._percentile(ordered, 95) / 1000,
            "p99_us": self._percentile(ordered, 99) / 1000,
        }
