# ChronosMatch Testing Plan

## 1. Objective

This document describes the testing approach for the ChronosMatch matching engine, order model, market simulator, latency monitor, and shared-memory ring buffer. The goal is to verify expected behaviour and identify regressions when changes are introduced.

## 2. Running the Tests

Activate the project's Python virtual environment and run:

```bash
python -m pytest -v
```

## 3. Existing Test Coverage

The latest observed test run completed with **45 passing test cases and 0 failures**. The following sections summarize the test coverage identified from the existing test descriptions and the latest terminal output.

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

## 7. Current Baseline

- **Date:** October 12, 2026.
- **Command:** `python -m pytest -v`.
- **Observed result:** 45 tests passed, 0 failures.
- **Reported execution time:** Approximately 0.32 seconds in the latest run.
- **Purpose:** Regression verification of the current local test suite, including ring-buffer, integration, simulator, and latency-monitor coverage.

The baseline should be updated whenever a new test run produces a different result. Confirm that the local branch is synchronized with the latest `main` before treating this result as the baseline for the latest remote code.