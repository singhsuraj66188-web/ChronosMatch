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

## Repeated benchmark runs — 12 October 2026

Environment: Windows 10, Python 3.14.7, local development machine.

Workload: 1,000 resting sell orders followed by 1,000 non-crossing buy submissions. Each run measures the buy submissions.

| Run | Median latency | P95 latency | P99 latency |
|---|---:|---:|---:|
| 1 | 2.10 us | 2.70 us | 3.80 us |
| 2 | 2.40 us | 4.50 us | 38.10 us |
| 3 | 2.30 us | 2.80 us | 4.50 us |
| 4 | 2.30 us | 4.00 us | 5.70 us |
| 5 | 4.30 us | 11.60 us | 25.60 us |

### Observations

- Median latency ranged from 2.10 to 4.30 µs.
- P95 latency ranged from 2.70 to 11.60 µs.
- P99 latency ranged from 3.80 to 38.10 µs.
- Tail latency varied noticeably between runs. Background system activity and runtime overhead are possible contributors, but the cause has not been established.

### Interpretation and limitations

These measurements are local Python microbenchmark results, not end-to-end trading-pipeline latency. They are preliminary and do not establish a general performance guarantee. Further repeated testing, crossing-order benchmarks, and separate shared-memory IPC measurements are required before evaluating the end-to-end 50 µs target.