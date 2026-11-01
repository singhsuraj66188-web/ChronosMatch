# IPC Ring Buffer Binary Protocol

## Status

This document describes the current implementation in `ipc/ring_buffer.py` and records the confirmed protocol contract below. Changes to the binary layout require team agreement and a versioned protocol revision.

## File layout

The file begins with a one-byte locking region, followed by a 16-byte header and a fixed-capacity record array.
Locking is platform-specific:
- **Windows:** `msvcrt.locking()` locks the reserved byte at offset 0.
- **POSIX/Linux:** `fcntl.flock()` locks the file, not just the reserved byte.

| Region or field | Offset / size | Encoding and meaning |
|---|---|---|
| Locking region | Offset 0, 1 byte | Reserved byte used by Windows locking; POSIX/Linux locking applies to the file |
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

## IPC Reliability Verification — Day 22

The following records the historical verification performed on Day 22. These results are historical evidence, not the Day 23 test results.

### Historical test results

- Focused IPC tests:
  `python -m pytest tests/test_ring_buffer.py tests/test_ring_buffer_integration.py -q`
  **62 passed in 11.20s**
- Full test suite:
  `python -m pytest -q`
  **112 passed in 7.73s**
- `git diff --check`: clean.

### Reliability coverage reviewed

- Empty and full buffer behavior, record round-trip, and wraparound.
- Record ordering and preservation of sequence, timestamp, price, quantity, and side.
- Concurrent producer-consumer operations.
- Same-instance and separate-instance concurrent writers.
- Lock release after exceptions, unlock failures, and temporary Windows lock contention.
- Reopening buffers while preserving records.
- Close waiting for active operations, concurrent close, and cleanup retries.
- Failed-write retry, retry exhaustion, and preservation of unread records.
- Consumer shutdown draining pending records.
- Consumer failure propagation and preservation of original processing errors during cleanup.
- Simulator integration and duplicate or decreasing sequence/timestamp rejection.

### Historical limitations

- No reproducible IPC reliability defect was identified during the Day 22 review.
- No implementation changes or additional regression tests were made.
- Power-loss recovery, forced process termination, and prolonged production-scale stress were not established by those test runs.
- Multi-symbol binary-record storage was not tested or introduced. The integration path uses `SIM` separately from the binary record.
- Automated test results do not guarantee against all runtime or hardware failures.

## IPC Reliability Verification — Day 23

### Environment

- Base commit: `964da23e675df7f06e9d478a021248eb2599bd90`
- Platform: Windows 11, 64-bit AMD64
- Python: 3.14.2

### Fresh test results

- Focused IPC tests:
  `python -m pytest tests/test_ring_buffer.py tests/test_ring_buffer_integration.py -q`
  **62 passed in 3.54s**
- Full test suite:
  `python -m pytest -q`
  **112 passed in 3.64s**