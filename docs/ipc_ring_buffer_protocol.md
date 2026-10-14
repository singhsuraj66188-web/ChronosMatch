# IPC Ring Buffer Binary Protocol

## Status

This document describes the current implementation in `ipc/ring_buffer.py` and records the confirmed protocol contract below. Changes to the binary layout require team agreement and a versioned protocol revision.

## File layout

The file begins with a one-byte locking region, followed by a 16-byte header and a fixed-capacity record array.

| Region or field | Offset / size | Encoding and meaning |
|---|---|---|
| Locking region | Offset 0, 1 byte | Used by platform-specific file locking |
| Write sequence counter | Offset 1, 8 bytes | Unsigned 64-bit integer, little-endian |
| Read sequence counter | Offset 9, 8 bytes | Unsigned 64-bit integer, little-endian |
| Record array | Offset 17 | Fixed-capacity array of 28-byte records |

The header format is `<QQ`. The record format is `<QQIIB3x`.

The total file size is `17 + 28 × capacity` bytes. The configured capacity must be at least two and must match when reopening an existing file.

## Record fields

| Field | Size | Valid range / meaning |
|---|---:|---|
| `sequence` | 8 bytes | Unsigned 64-bit integer; assigned by the buffer |
| `timestamp_ns` | 8 bytes | Unsigned 64-bit integer; timestamp in nanoseconds |
| `price_ticks` | 4 bytes | Positive unsigned 32-bit integer; price represented in ticks |
| `quantity` | 4 bytes | Positive unsigned 32-bit integer |
| `side` | 1 byte | `1 = BUY`, `2 = SELL` in the current API |
| Padding | 3 bytes | Reserved padding; not application data |

Unsigned 64-bit fields can represent values from 0 through `2^64 - 1`. The price and quantity fields are 32-bit unsigned integers, with the current API requiring values from 1 through `2^32 - 1`.

## Read and write behavior

- `write()` returns `True` when a record is written.
- `write()` returns `False` when the buffer is full.
- `read()` returns a record dictionary when data is available and `None` when the buffer is empty.
- Records use monotonically increasing sequence counters and wrap around the fixed-capacity slot array.
- A platform-specific lock protects shared counter and record updates.

## Lifecycle and platform considerations

- `create=True` creates or truncates the file and initializes the buffer.
- Reopening without `create=True` requires an existing file with the expected size.
- `close()` flushes and closes the memory map and file.
- The implementation uses `msvcrt` locking on Windows and `fcntl.flock` on other platforms.



## Confirmed protocol contract

The following details have been confirmed with Suraj:

- **Record format:** `<QQIIB3x`, little-endian, 28 bytes per record.
- **Sequence:** unsigned 64-bit integer, assigned by the ring buffer starting at 0.
- **Timestamp:** unsigned 64-bit integer from the simulator's `time.perf_counter_ns()`. This is a monotonic performance-counter reading, not Unix-epoch time. Latency measurements must use compatible clock domains.
- **Price ticks:** unsigned 32-bit integer, from 1 through `2^32 - 1`.
- **Quantity:** unsigned 32-bit integer, from 1 through `2^32 - 1`.
- **Side:** unsigned 8-bit integer; `1 = BUY`, `2 = SELL`.
- **Reserved bytes:** three padding bytes, written as zero.
- **Symbol:** remains `SIM` at the integration layer; it is not part of the binary record.
- **Compatibility:** changes to the binary layout require team agreement and a versioned protocol revision.

The existing full/empty behavior and Windows/Linux locking implementation remain unchanged.