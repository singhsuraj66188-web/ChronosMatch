from __future__ import annotations

import mmap
import os
import struct
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_HEADER = struct.Struct("<QQ")
_RECORD = struct.Struct("<QQIIB3x")

_LOCK_OFFSET = 0
_HEADER_OFFSET = 1
_DATA_OFFSET = _HEADER_OFFSET + _HEADER.size


class RingBuffer:
    """Prototype file-backed ring buffer for one producer and one consumer.

    Platform-specific locking is used to protect shared counter updates.
    Side: 1 = BUY, 2 = SELL.
    Price is an integer tick value, not a floating-point number.
    """

    def __init__(
        self,
        path: str | Path,
        capacity: int = 64,
        *,
        create: bool = False,
    ):
        if capacity < 2:
            raise ValueError("capacity must be at least 2")

        self.path = Path(path)
        self.capacity = capacity
        self._size = _DATA_OFFSET + capacity * _RECORD.size
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if create:
            with open(self.path, "w+b") as file:
                file.truncate(self._size)
                file.flush()
        elif not self.path.exists():
            raise FileNotFoundError(self.path)

        self._file = open(self.path, "r+b")

        actual_size = os.fstat(self._file.fileno()).st_size
        if actual_size != self._size:
            self._file.close()
            raise ValueError(
                f"Expected a {self._size}-byte buffer, "
                f"but found {actual_size} bytes. "
                "Use the same capacity when reopening."
            )

        self._map = mmap.mmap(
            self._file.fileno(),
            self._size,
            access=mmap.ACCESS_WRITE,
        )

        if create:
            self._map[:] = b"\x00" * self._size
            self._map[_HEADER_OFFSET:_DATA_OFFSET] = _HEADER.pack(0, 0)
            self._map.flush()


    def _lock(self) -> None:
        self._file.seek(_LOCK_OFFSET)
        if os.name == "nt":
            msvcrt.locking(self._file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)

    def _unlock(self) -> None:
        self._file.seek(_LOCK_OFFSET)
        if os.name == "nt":
            msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)


    def _counters(self) -> tuple[int, int]:
        return _HEADER.unpack(self._map[_HEADER_OFFSET:_DATA_OFFSET])

    def write(
        self,
        *,
        timestamp_ns: int,
        price_ticks: int,
        quantity: int,
        side: int,
    ) -> bool:
        if timestamp_ns < 0 or price_ticks < 1:
            raise ValueError("timestamp and price are invalid")
        if quantity < 1 or side not in (1, 2):
            raise ValueError("quantity or side is invalid")

        self._lock()
        try:
            write_seq, read_seq = self._counters()

            if write_seq - read_seq >= self.capacity:
                return False

            slot = write_seq % self.capacity
            offset = _DATA_OFFSET + slot * _RECORD.size

            self._map[offset:offset + _RECORD.size] = _RECORD.pack(
                write_seq,
                timestamp_ns,
                price_ticks,
                quantity,
                side,
            )

            self._map[_HEADER_OFFSET:_DATA_OFFSET] = _HEADER.pack(
                write_seq + 1,
                read_seq,
            )
            return True
        finally:
            self._unlock()

    def read(self) -> dict | None:
        self._lock()
        try:
            write_seq, read_seq = self._counters()

            if read_seq >= write_seq:
                return None

            slot = read_seq % self.capacity
            offset = _DATA_OFFSET + slot * _RECORD.size

            seq, timestamp_ns, price_ticks, quantity, side = _RECORD.unpack(
                self._map[offset:offset + _RECORD.size]
            )

            if seq != read_seq:
                raise RuntimeError("Ring-buffer sequence mismatch")

            self._map[_HEADER_OFFSET:_DATA_OFFSET] = _HEADER.pack(
                write_seq,
                read_seq + 1,
            )

            return {
                "sequence": seq,
                "timestamp_ns": timestamp_ns,
                "price_ticks": price_ticks,
                "quantity": quantity,
                "side": side,
            }
        finally:
            self._unlock()

    def close(self) -> None:
        self._map.flush()
        self._map.close()
        self._file.close()

    def __enter__(self) -> "RingBuffer":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
