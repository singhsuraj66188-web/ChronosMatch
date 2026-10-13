# IPC Ring Buffer Binary Protocol

## Status

This document describes the current implementation in `ipc/ring_buffer.py`. It is not confirmation that all interface decisions have been approved by Suraj and Joanna. Obtain their confirmation before treating this format as a finalized cross-process contract.

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

## Decisions requiring confirmation

Confirm with Suraj and Joanna:

1. Whether this byte layout, little-endian encoding, and field widths are the agreed interface.
2. Whether timestamps are Unix-epoch nanoseconds or another nanosecond-based clock. The code specifies units but does not establish the epoch.
3. Whether price ticks and quantity must be strictly positive.
4. Whether side values `1` and `2` are the agreed BUY/SELL encoding.
5. Whether the one-byte lock region and locking approach meet the intended cross-platform contract.
6. Whether reserved padding bytes must be zero and how protocol versioning should work.

Do not change the binary layout without agreement from the interface owners.
