# ChronosMatch Testing Plan

## 1. Objective

This document describes the testing approach for the ChronosMatch matching engine, order model, market simulator, latency monitor, and shared-memory ring buffer. The goal is to verify expected behaviour and identify regressions when changes are introduced.

## 2. Running the Tests

Activate the project's Python virtual environment and run:

```bash
python -m pytest -v
```

## 3. Existing Test Coverage

The latest verified Day 9 local run on Windows with Python 3.14.8 completed with 74 passed and 0 failures in 2.12 seconds using python -m pytest -v. This is the current local result; older runs below are retained as historical evidence.

### Order Validation (`tests/test_orders.py`)

- Valid buy order creation.
- Rejection of invalid orders, including invalid order IDs, prices, and quantities.
- Rejection of invalid order sides.

### Matching Engine (`tests/test_matching_engine.py`)

- Buy orders matching resting sell orders at the resting price.
- Sell orders matching resting buy orders at the resting price.
- Non-crossing orders not trading.
- Best-price order matching first.
- Matching against multiple resting orders.
- Rejection of duplicate active order IDs.
- Timestamp priority for orders at the same price.
- Order ID as a tie-breaker when price and timestamp are identical.

### Market Simulator and Latency Monitor (`tests/test_simulator.py`)

- Verification that the simulator generates the requested number of ticks.
- Verification of sequential tick numbers and positive price and quantity values.
- Rejection of negative tick counts.
- Rejection of invalid intervals, including negative, infinite, and NaN values.
- Verification that the simulator accepts a zero interval.
- Verification of reproducible simulator output when using the same seed.
- Verification of latency summary counts and median.
- Verification of the summary of an empty latency monitor.
- Rejection of negative latency durations.
- Verification of nearest-rank p95 and p99 latency calculations.
- Verification that the latency monitor maintains a bounded sample window.
- Verification that zero latency duration is accepted.
- Rejection of invalid latency window sizes.

### Shared-Memory Ring Buffer (`tests/test_ring_buffer.py` and `tests/test_ring_buffer_integration.py`)

- Writing and reading tick records.
- Reading from an empty buffer.
- Full-buffer rejection and wraparound behaviour.
- Rejection of invalid tick data.
- Preservation of records after closing and reopening the buffer.
- Rejection of a capacity mismatch when reopening an existing buffer.
- Rejection of capacities below two.
- Preservation of values and order during successful transfers.
- Handling of empty input.
- Handling of full-buffer conditions and retry behaviour.
- Reporting retry exhaustion.
- Rejection of invalid retry configurations.
- Ring-buffer cleanup and integration behaviour.
- Verification of the IPC matching adapter integration tests.
- Five adapter integration tests passed in the latest observed run.

### Day 9 Coverage Evidence Matrix

| Area | Test file(s) | Evidence / status | Remaining gap |
|---|---|---|---|
| Order validation | `tests/test_orders.py`, `tests/test_matching_engine.py` | Order ID, price, quantity, and side validation are covered. | Review additional boundary cases if needed. |
| Matching engine | `tests/test_matching_engine.py` | Price matching, best-price selection, multiple matches, duplicate IDs, and priority rules are covered. | Review standalone coverage for fully filled order removal. |
| Simulator and latency monitor | `tests/test_simulator.py` | Tick generation, input validation, reproducibility, and latency calculations are documented as covered. | Review exact assertions before extending coverage. |
| Ring buffer | `tests/test_ring_buffer.py`, `tests/test_ring_buffer_integration.py` | Buffer operations, capacity, wraparound, lifecycle, and integration are documented as covered. | Investigate previously reported intermittent concurrency timeouts. |
| IPC matching adapter | `tests/test_ipc_matching_integration.py` | Five tests collected. | Review producer-consumer edge cases. |
| End-to-end pipeline | `tests/test_end_to_end.py` | Verifies transferred records, expected trades, and final order-book state. | Check repeated-run determinism if required by the E2E plan. |

#### Latest Day 9 Local Verification

- **Platform:** Windows (`win32`)
- **Python:** 3.14.8
- **Command:** `python -m pytest -v`
- **Result:** 74 passed, 0 failures
- **Duration:** 2.12 seconds
- **Collection check:** 74 tests collected

The collection check confirms test discovery; the full-suite run confirms that all 74 tests passed. This result does not establish exhaustive coverage of every protocol or concurrency scenario.

## 4. Regression Testing

Run the complete test suite after modifying the order model, matching engine, simulator, latency monitor, or ring buffer. Existing tests should continue to pass unless an intentional behaviour change is introduced and reviewed.

New tests should be added when new functionality or previously untested behaviour is introduced.

## 5. Recording Results

For each test run, record:

- Date of the test run.
- Code changes being tested.
- Command used.
- Number of tests passed and failed.
- Any errors or unexpected behaviour.

## 6. Future Testing

Additional tests should be considered as the implementation evolves, including:

- Order cancellation and removal of cancelled orders from the active book.
- Partial fills and remaining quantities after matching.
- Order-book state after completed trades.
- Matching-engine behaviour for empty books and additional boundary cases.
- Simulator behaviour for zero ticks and boundary values for valid intervals.
- Latency percentile calculations for small sample sizes and rolling-window boundaries.

These are candidate areas for additional testing. Confirm the intended behaviour in the implementation before adding new tests or describing them as existing coverage.

**Deterministic End-to-End IPC Matching Test Checklist**

- [ ] Generate deterministic market ticks using a fixed simulator seed.
- [ ] Transfer ticks through the shared-memory ring buffer.
- [ ] Read records and submit them through the matching consumer.
- [ ] Verify the expected trade price, quantity, and buy/sell order IDs.
- [ ] Verify the remaining quantities and final order-book state.
- [ ] Confirm the test passes consistently across repeated runs.
- [ ] Coordinate with Joanna before changing or extending consumer integration code.

## 7. Current Baseline

- **Date:** October 15, 2026.
- **Current main baseline date:** October 15, 2026.
- **Current main command:** `.\.venv\Scripts\python.exe -m pytest -v`.
- **Current main result:** 74 tests passed, 0 failures, in 4.63 seconds.
- **Current main environment:** Windows, Python 3.14.7.
- **Purpose:** Regression verification of the current test suite, including order validation, matching-engine behaviour, ring-buffer operations, IPC integration, end-to-end simulator-to-matching-engine processing, and latency-monitor coverage.

This baseline reflects the observed local test run on the updated main branch. Re-run the full test suite after subsequent changes and update this section whenever a new verified test run produces a different result.

### Day 6 IPC reliability verification

- **Branch:** `test/day6-ipc-reliability`.
- **Environment:** Windows, Python 3.14.2, pytest 9.1.1.
- **Full-suite command:** `python -m pytest -v`.
- **Full-suite result:** 72 tests passed, 0 failures, in 5.57 seconds.
- **IPC-focused command:** `python -m pytest -v tests/test_ring_buffer.py tests/test_ipc_matching_integration.py`.
- **IPC-focused result:** 26 tests passed, 0 failures, in 9.11 seconds.
- **Concurrency repeat check:** `test_ring_buffer_supports_concurrent_producer_and_consumer` passed in 10 consecutive individual runs.
- **Git checks:** The Day 6 branch was clean, and `git diff --check` reported no whitespace errors.

These results record the Day 6 runs before merging the latest main branch. Although the concurrency test passed in 10 consecutive runs, earlier intermittent timeouts remain unresolved. Keep this reliability concern open until its cause is understood and the behavior is verified consistently.