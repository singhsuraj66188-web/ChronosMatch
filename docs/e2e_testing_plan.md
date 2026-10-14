# ChronosMatch End-to-End Testing Plan

## Objective
Verify the flow from market simulator ticks through the shared-memory ring buffer and matching consumer into the matching engine.

## Test Flow
1. Initialise the market simulator with deterministic inputs or a fixed seed.
2. Generate suitable ticks with known timestamps, prices, quantities, and sides.
3. Transfer the ticks through the existing simulator-to-ring-buffer integration.
4. Read each record from the ring buffer and submit it through the matching consumer.
5. Verify the resulting trades and final order-book state.

## Expected Trade Scenario
- First record: SELL, price 10000, quantity 2, timestamp 100.
- Second record: BUY, price 10100, quantity 1, timestamp 200.
- Expected result: one trade at the resting sell price of 10000, quantity 1.
- Expected remaining state: the sell order remains in the ask book with quantity 1; no remaining buy order.

## Verification Checklist
- [ ] Simulator output is reproducible for the chosen test inputs.
- [ ] Ring-buffer records preserve the expected field values and order.
- [ ] The consumer converts records into valid matching-engine orders.
- [ ] The expected trade price, quantity, and order IDs are correct.
- [ ] Remaining quantities and final order-book state are correct.
- [ ] Repeated runs produce the same result.
- [ ] Buffer cleanup occurs correctly.

## Coverage Gaps and Coordination
- Confirm the exact simulator-to-ring-buffer integration interface.
- Confirm with Joanna how the consumer should be connected before changing her implementation.
- Add and run an automated end-to-end test only after confirming the integration interfaces.

This document describes planned verification. It does not claim that the complete end-to-end test has already been implemented or executed.