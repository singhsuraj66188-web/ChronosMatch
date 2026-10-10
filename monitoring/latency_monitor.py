
from __future__ import annotations

import statistics


class LatencyMonitor:
    """Collect duration samples measured in nanoseconds."""

    def __init__(self) -> None:
        self._samples_ns: list[int] = []

    def record(self, duration_ns: int) -> None:
        if duration_ns < 0:
            raise ValueError("duration_ns cannot be negative")
        self._samples_ns.append(duration_ns)

    @staticmethod
    def _percentile(
        values: list[int],
        percentile: float,
    ) -> int:
        if not values:
            return 0

        index = int((percentile / 100) * len(values))
        index = min(index, len(values) - 1)
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
