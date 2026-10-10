# ChronosMatch Testing Plan

## 1. Objective

This document describes the testing approach for the ChronosMatch matching engine and order model. The goal is to verify expected behaviour and identify regressions when changes are introduced.

## 2. Running the Tests

Activate the project's Python virtual environment and run:

```bash
python -m pytest -v
```

## 3. Existing Test Coverage

The current test suite contains 13 passing tests.

### Order Validation (`tests/test_orders.py`)

- Valid buy order creation.
- Rejection of invalid orders.
- Rejection of invalid order sides.

### Matching Engine (`tests/test_matching_engine.py`)

- Buy orders matching resting sell orders at the resting price.
- Sell orders matching resting buy orders at the resting price.
- Non-crossing orders not trading.
- Best-price order matching first.
- Matching against multiple resting orders.
- Rejection of duplicate active order IDs.

## 4. Regression Testing

Run the complete test suite after modifying the order model or matching engine. Existing tests should continue to pass unless an intentional behaviour change is introduced and reviewed.

New tests should be added when new functionality or previously untested behaviour is introduced.

## 5. Recording Results

For each test run, record:

- Date of the test run.
- Code changes being tested.
- Command used.
- Number of tests passed and failed.
- Any errors or unexpected behaviour.

## 6. Future Testing

Additional tests should be considered as the implementation evolves, including partial fills, order cancellation, and edge cases in matching behaviour. These should be added after verifying the supported behaviour in the implementation.

## 7. Current Baseline

Date: October 10, 2026

Command: python -m pytest -v

Result: 13 tests passed, 0 failures.

Purpose: Initial baseline test run for the current test suite.