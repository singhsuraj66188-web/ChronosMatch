# ChronosMatch Benchmark Results

## Environment

- OS: Windows 10
- Python: 3.14.7, 64-bit
- Compiler: Microsoft Visual Studio C++ Build Tools
- Benchmark: `benchmarks/benchmark_engine.py`

## Baseline 1 â€” Before order-book optimization

Workload: 1,000 resting sell orders, followed by 1,000 non-crossing buy submissions.

| Metric | Result |
|---|---:|
| Median latency | 167.85 Âµs |
| P95 latency | 250.80 Âµs |
| P99 latency | 465.80 Âµs |

The original implementation sorted the opposite-side order book on every submission.

## Baseline 2 â€” Sorted order-book implementation

Same intended workload.

| Metric | Result |
|---|---:|
| Median latency | 2.50 Âµs |
| P95 latency | 4.80 Âµs |
| P99 latency | 8.90 Âµs |

The updated implementation maintains price-time ordering as orders are inserted, avoiding a complete sort on every submission.

## Observed change

| Metric | Before | After |
|---|---:|---:|
| Median | 167.85 Âµs | 2.50 Âµs |
| P95 | 250.80 Âµs | 4.80 Âµs |
| P99 | 465.80 Âµs | 8.90 Âµs |

These are single-run, local microbenchmark measurements. They indicate a substantial improvement for this workload but are not a general performance guarantee.

## Limitations and next steps

- Repeat benchmarks across multiple runs and report variation.
- Add tests for equal-price time priority, partial fills, and active-order bookkeeping.
- Benchmark crossing orders and order-book growth separately.
- Compare the Python reference engine with the Cython implementation.
- Measure ring-buffer IPC and full-pipeline latency independently.
- Do not claim the end-to-end 50 Âµs target is achieved until it is reproducibly measured.

## Repeated benchmark runs â€” 12 October 2026

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

- Median latency ranged from 2.10 to 4.30 Âµs.
- P95 latency ranged from 2.70 to 11.60 Âµs.
- P99 latency ranged from 3.80 to 38.10 Âµs.
- Tail latency varied noticeably between runs. Background system activity and runtime overhead are possible contributors, but the cause has not been established.

### Interpretation and limitations

These measurements are local Python microbenchmark results, not end-to-end trading-pipeline latency. They are preliminary and do not establish a general performance guarantee. Further repeated testing, crossing-order benchmarks, and separate shared-memory IPC measurements are required before evaluating the end-to-end 50 Âµs target.
## Day 7 — Crossing and non-crossing engine benchmark

Date: 16 October 2026

Environment: Windows 10, Python 3.14.7, 64-bit.

Benchmark: `benchmarks/benchmark_engine.py`

Each run measured 1,000 submissions per scenario. Initial order-book setup, order construction, and post-trade correctness checks were excluded from the timed interval.

### Scenario A — Non-crossing submissions

1,000 resting sell orders were prepared before measurement. The benchmark then measured 1,000 buy submissions priced below the resting asks. These orders did not execute trades.

| Run | Median (us) | P95 (us) | P99 (us) |
|---|---:|---:|---:|
| 1 | 2.20 | 2.50 | 3.70 |
| 2 | 2.30 | 2.50 | 3.90 |
| 3 | 2.30 | 2.50 | 3.60 |

### Scenario B — Actual trade execution

1,000 resting sell orders were prepared before measurement. The benchmark then measured 1,000 crossing buy submissions, each expected to execute one trade for one unit at the resting price.

| Run | Median (us) | P95 (us) | P99 (us) |
|---|---:|---:|---:|
| 1 | 1.90 | 2.10 | 2.80 |
| 2 | 3.00 | 4.60 | 20.10 |
| 3 | 2.20 | 4.20 | 17.40 |

### Observations

- Non-crossing submission latency was comparatively stable across these three runs.
- Trade execution showed greater run-to-run variation, particularly at P99.
- These are local Python microbenchmark measurements. They are not measurements of Cython execution, shared-memory IPC, or end-to-end pipeline latency.
- Three runs are an initial baseline, not sufficient evidence of stable production performance.
- Background system activity and runtime effects may contribute to variation, but their causes have not been established.

### Limitations and next steps

- Repeat measurements over more runs and report variation.
- Benchmark growing-book insertion and multi-order partial fills separately.
- Measure IPC and end-to-end pipeline latency independently.
- Compare the Python reference engine with the Cython implementation when the relevant benchmark is ready.
- Do not claim the end-to-end target of under 50 us is achieved without reproducible full-pipeline measurements.

## Day 11 — End-to-End Pipeline Benchmark

**Date:** 20 October 2026

**Environment:** Windows 10, Python 3.14.7, 64-bit.

**Benchmark:** `benchmarks/benchmark_e2e.py`

**Workload:** 1,000 synthetic market ticks with ring-buffer capacity 2,048. The benchmark exercised the simulator-to-ring-buffer-to-matching-engine pipeline.

### Results

| Metric | Run 1 | Run 2 |
|---|---:|---:|
| Generated ticks | 1,000 | 1,000 |
| Successful writes | 1,000 | 1,000 |
| Successful reads | 1,000 | 1,000 |
| Failed writes | 0 | 0 |
| Trades executed | 787 | 787 |
| Total elapsed time | 0.075833 s | 0.056258 s |
| Reported throughput | 13,186.92 ticks/s | 17,775.28 ticks/s |
| Median write-to-read latency | 133.50 µs | 133.25 µs |
| P95 write-to-read latency | 160.50 µs | 154.20 µs |
| P99 write-to-read latency | 190.00 µs | 216.00 µs |

### Observations

- Both runs processed all 1,000 ticks, with no failed writes and 1,000 successful reads.
- Both runs executed 787 trades.
- Median write-to-read latency was similar across the two runs.
- P95 was slightly lower in Run 2, while P99 was higher, indicating some variation in tail latency.
- Reported throughput differed between runs. More repeated measurements are needed to establish a representative performance baseline.

### Interpretation and limitations

The latency percentiles measure ring-buffer write-to-read time; they do not measure the complete per-tick path through matching. Total elapsed time includes pipeline setup and shutdown, and the workload uses synthetic ticks rather than real exchange data.

These two runs are preliminary measurements from a local Windows development environment. They do not establish that the end-to-end latency target of under 50 µs has been achieved.

### Next steps

- Repeat the benchmark across additional runs and summarize variation.
- Investigate tail-latency variability under controlled conditions.
- Keep matching-engine, IPC, and full-pipeline measurements separate.
- Verify that the benchmark and its assumptions remain valid against the latest test suite and ring-buffer implementation.
