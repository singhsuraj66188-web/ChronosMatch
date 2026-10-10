# ChronosMatch Benchmark Results

## Environment

- OS: Windows 10
- Python: 3.14.7, 64-bit
- Compiler: Microsoft Visual Studio C++ Build Tools
- Benchmark: `benchmarks/benchmark_engine.py`

## Baseline 1 — Before order-book optimization

Workload: 1,000 resting sell orders, followed by 1,000 non-crossing buy submissions.

| Metric | Result |
|---|---:|
| Median latency | 167.85 µs |
| P95 latency | 250.80 µs |
| P99 latency | 465.80 µs |

The original implementation sorted the opposite-side order book on every submission.

## Baseline 2 — Sorted order-book implementation

Same intended workload.

| Metric | Result |
|---|---:|
| Median latency | 2.50 µs |
| P95 latency | 4.80 µs |
| P99 latency | 8.90 µs |

The updated implementation maintains price-time ordering as orders are inserted, avoiding a complete sort on every submission.

## Observed change

| Metric | Before | After |
|---|---:|---:|
| Median | 167.85 µs | 2.50 µs |
| P95 | 250.80 µs | 4.80 µs |
| P99 | 465.80 µs | 8.90 µs |

These are single-run, local microbenchmark measurements. They indicate a substantial improvement for this workload but are not a general performance guarantee.

## Limitations and next steps

- Repeat benchmarks across multiple runs and report variation.
- Add tests for equal-price time priority, partial fills, and active-order bookkeeping.
- Benchmark crossing orders and order-book growth separately.
- Compare the Python reference engine with the Cython implementation.
- Measure ring-buffer IPC and full-pipeline latency independently.
- Do not claim the end-to-end 50 µs target is achieved until it is reproducibly measured.
