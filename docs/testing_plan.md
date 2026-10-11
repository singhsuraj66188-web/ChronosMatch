# ChronosMatch Testing Plan

## 1. Objective

This document describes the testing approach for the ChronosMatch matching engine, order model, market simulator, and latency monitor. The goal is to verify expected behaviour and identify regressions when changes are introduced.

## 2. Running the Tests

Activate the project's Python virtual environment and run:

```bash
python -m pytest -v
```

## 3. Existing Test Coverage

The current test suite contains 20 passing test cases.

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
- Rejection of a negative tick count.
- Verification of latency summary count and median.
- Verification of the summary of an empty latency monitor.
- Rejection of negative latency durations.

## 4. Regression Testing

Run the complete test suite after modifying the order model, matching engine, simulator, or latency monitor. Existing tests should continue to pass unless an intentional behaviour change is introduced and reviewed.

New tests should be added when new functionality or previously untested behaviour is introduced.

## 5. Recording Results

For each test run, record:

- Date of the test run.
- Code changes being tested.
- Command used.
- Number of tests passed and failed.
- Any errors or unexpected behaviour.

## 6. Future Testing

Additional tests should be considered as the implementation evolves, including order cancellation and other edge cases not covered by the current test suite. New tests should be added after verifying the supported behaviour in the implementation.

## 7. Current Baseline

- **Date:** October 11, 2026
- **Command:** `python -m pytest -v`
- **Result:** 20 tests passed, 0 failures.
- **Purpose:** Baseline test run for the current test suite.