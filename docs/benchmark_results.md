# ChronosMatch Benchmark Results

## 1. Purpose

This document records the available matching-engine and end-to-end pipeline benchmark results for ChronosMatch.

The results are local development measurements. They are useful for comparing runs and identifying performance changes, but they are not proof of production trading performance.

**Important distinction:**
- **Matching-engine latency** measures the timed matching-engine operation in the engine benchmark.
- **Write-to-read latency** measures the time between writing a tick to the shared-memory ring buffer and reading it.
- **Full end-to-end latency** would measure the complete path from tick generation through ring-buffer communication and matching-engine processing for each tick.

These measurements are different and must not be treated as interchangeable.

## 2. Benchmark Environment

The environment recorded for the existing benchmarks is:

- Operating system: Windows 10
- Python: 3.14.7, 64-bit
- Compiler: Microsoft Visual Studio C++ Build Tools
- Matching-engine benchmark: `benchmarks/benchmark_engine.py`
- End-to-end pipeline benchmark: `benchmarks/benchmark_e2e.py`

These environment details describe the recorded benchmark runs. They should not be assumed to describe every later test or benchmark run.

## 3. Matching-Engine Benchmark: Initial Comparison

The matching-engine benchmark compared the original implementation with the sorted implementation.

### Workload

- Create 1,000 resting sell orders.
- Submit 1,000 non-crossing buy orders.
- Measure the matching-engine submission operation.

### Results

| Metric | Before optimization | Sorted implementation |
|---|---:|---:|
| Median latency | 167.85 µs | 2.50 µs |
| P95 latency | 250.80 µs | 4.80 µs |
| P99 latency | 465.80 µs | 8.90 µs |

The recorded results show a substantial reduction in matching-engine submission latency for this specific workload.

These figures are matching-engine microbenchmark results. They do not include the complete simulator-to-ring-buffer-to-matching-engine pipeline.

## 4. Matching-Engine Repeated Runs — 12 October 2026

Five local benchmark runs were recorded for the non-crossing order-submission workload.

| Run | Median (µs) | P95 (µs) | P99 (µs) |
|---|---:|---:|---:|
| 1 | 2.10 | 2.70 | 3.80 |
| 2 | 2.40 | 4.50 | 38.10 |
| 3 | 2.30 | 2.80 | 4.50 |
| 4 | 2.30 | 4.00 | 5.70 |
| 5 | 4.30 | 11.60 | 25.60 |

The median latency remained low across these runs, while some runs showed higher tail latency.

The cause of the tail-latency variation has not been established. These local measurements should not be used to claim a guaranteed latency under production conditions.

## 5. Matching-Engine Benchmark — 16 October 2026

The benchmark used `benchmarks/benchmark_engine.py` with 1,000 submissions per scenario.

Order construction, scenario setup, and correctness checks were excluded from the timed interval.

### 5.1 Non-crossing orders

The workload created 1,000 resting sell orders and then submitted 1,000 non-crossing buy orders.

| Run | Median (µs) | P95 (µs) | P99 (µs) |
|---|---:|---:|---:|
| 1 | 2.20 | 2.50 | 3.70 |
| 2 | 2.30 | 2.50 | 3.90 |
| 3 | 2.30 | 2.50 | 3.60 |

### 5.2 Crossing orders

The workload created 1,000 resting sell orders and then submitted 1,000 crossing buy orders. Each crossing buy order was expected to produce one trade at the resting order's price.

| Run | Median (µs) | P95 (µs) | P99 (µs) |
|---|---:|---:|---:|
| 1 | 1.90 | 2.10 | 2.80 |
| 2 | 3.00 | 4.60 | 20.10 |
| 3 | 2.20 | 4.20 | 17.40 |

### Interpretation

These measurements provide an initial local baseline for non-crossing and crossing matching-engine workloads. Three runs per scenario are not enough to establish stable production performance.

This benchmark does not measure Cython performance, shared-memory write-to-read latency, or full end-to-end pipeline latency.

## 6. End-to-End Pipeline Benchmark — 20 October 2026

### Benchmark setup

- Script: `benchmarks/benchmark_e2e.py`
- Workload: 1,000 synthetic market ticks
- Ring-buffer capacity: 2,048
- Pipeline: simulator → ring buffer → matching engine
- Recorded runs: 2

### Results

| Metric | Run 1 | Run 2 |
|---|---:|---:|
| Generated ticks | 1,000 | 1,000 |
| Successful writes | 1,000 | 1,000 |
| Successful reads | 1,000 | 1,000 |
| Failed writes | 0 | 0 |
| Trades | 787 | 787 |
| Total elapsed time (s) | 0.075833 | 0.056258 |
| Reported throughput (ticks/s) | 13,186.92 | 17,775.28 |
| Write-to-read samples | 1,000 | 1,000 |
| Median write-to-read latency (µs) | 133.50 | 133.25 |
| P95 write-to-read latency (µs) | 160.50 | 154.20 |
| P99 write-to-read latency (µs) | 190.00 | 216.00 |

### Interpretation and limitations

The pipeline exercised the simulator, ring buffer, and matching engine. However, the reported latency percentiles measure **ring-buffer write-to-read latency**, not the complete per-tick path through matching-engine processing.

Total elapsed time covers the benchmark's overall execution and includes setup and shutdown. It must not be presented as a per-tick end-to-end latency percentile.

The workload uses synthetic market ticks rather than real exchange data. Two runs are useful as an initial observation but are insufficient to establish a stable performance baseline.

## 7. End-to-End Pipeline Benchmark — 21 October 2026

### Benchmark setup

- Script: `benchmarks/benchmark_e2e.py`
- Workload: 1,000 synthetic market ticks
- Ring-buffer capacity: 2,048
- Pipeline: simulator → ring buffer → matching engine
- Recorded runs: 1

### Results

| Metric | Recorded result |
|---|---:|
| Generated ticks | 1,000 |
| Successful writes | 1,000 |
| Successful reads | 1,000 |
| Failed writes | 0 |
| Trades | 787 |
| Total elapsed time (s) | 0.085174 |
| Reported throughput (ticks/s) | 11,740.71 |
| Write-to-read samples | 1,000 |
| Median write-to-read latency (µs) | 135.80 |
| P95 write-to-read latency (µs) | 161.30 |
| P99 write-to-read latency (µs) | 249.20 |

### Interpretation and limitations

The run successfully processed 1,000 synthetic ticks, recorded 1,000 successful writes and reads, and reported 787 trades with no failed writes.

The reported median, P95, and P99 values are **write-to-read latency measurements**. They are not measurements of complete per-tick simulator-to-matching-engine latency.

The total elapsed time and reported throughput describe overall benchmark execution; they do not provide a full end-to-end latency distribution for individual ticks.

This result represents a single run, so it should be treated as an observation rather than a stable performance baseline. The workload is synthetic and does not establish performance with real exchange traffic.

## 8. Comparison of Recorded Pipeline Runs

| Date | Runs recorded | Median write-to-read latency | P95 write-to-read latency | P99 write-to-read latency |
|---|---:|---:|---:|---:|
| 20 October 2026 | 2 | 133.50 µs and 133.25 µs | 160.50 µs and 154.20 µs | 190.00 µs and 216.00 µs |
| 21 October 2026 | 1 | 135.80 µs | 161.30 µs | 249.20 µs |

These values are reported separately for each run. The available data does not establish a stable trend or explain the differences in tail latency.

The matching-engine microbenchmark results in earlier sections measure a different part of the system and should not be directly compared with these ring-buffer write-to-read measurements.

## 9. Measurement Limitations

The current evidence has the following limitations:

1. **Synthetic workload:** The pipeline benchmarks use generated ticks, not real exchange traffic.
2. **Limited repetitions:** The 21 October pipeline result contains only one recorded run.
3. **Different timing boundaries:** Matching-engine operation latency, ring-buffer write-to-read latency, total elapsed time, and throughput measure different things.
4. **No full end-to-end latency distribution:** The reported pipeline percentiles do not establish per-tick latency from simulator generation through matching-engine completion.
5. **Local environment:** The recorded results reflect local benchmark conditions and may vary with system load and environment.
6. **Tail-latency variation:** Some matching-engine runs have noticeably higher P95 or P99 values. The cause has not been established.
7. **Performance target not proven:** These results do not establish that the complete pipeline meets a 50 µs end-to-end latency target.

## 10. Recommended Next Steps

- Preserve the existing benchmark results as historical evidence.
- Run repeated benchmark trials before establishing a stable performance baseline.
- Keep matching-engine, write-to-read, and full end-to-end measurements clearly separated.
- If full end-to-end latency is required, ensure the measurement captures the complete path for each tick through matching-engine processing.
- Record the exact workload, timing boundaries, environment, and number of repetitions for future comparisons.
- Coordinate any benchmark-code changes with the relevant implementation owners.

## 11. Conclusion

The recorded matching-engine microbenchmarks show low submission latency for the tested workloads. The end-to-end pipeline runs also show successful processing of the synthetic tick workload.

However, the available pipeline latency percentiles measure ring-buffer write-to-read time, not the complete simulator-to-matching-engine path. More repeated measurements and an explicitly defined end-to-end timing boundary are needed before making stronger performance claims.

## 12. End-to-End Pipeline Benchmark — 22 October 2026

### Benchmark setup

- Script: `benchmarks/benchmark_e2e.py`
- Environment: Local Windows 10 development environment
- Workload: Synthetic market ticks
- Pipeline: Simulator → ring buffer → matching engine
- Ring-buffer capacity: 2,048 (default configuration)
- Recorded runs: Three runs with 1,000 ticks and one run with 10,000 ticks

### Results

| Metric | Run 1 (1,000 ticks) | Run 2 (1,000 ticks) | Run 3 (1,000 ticks) | Run 4 (10,000 ticks) |
|---|---:|---:|---:|---:|
| Generated ticks | 1,000 | 1,000 | 1,000 | 10,000 |
| Successful writes | 1,000 | 1,000 | 1,000 | 10,000 |
| Successful reads | 1,000 | 1,000 | 1,000 | 10,000 |
| Failed writes | 0 | 0 | 0 | 0 |
| Trades executed | 787 | 787 | 787 | 8,270 |
| Total elapsed time (s) | 0.765422 | 0.154750 | 0.133453 | 0.744490 |
| Reported throughput (ticks/s) | 1,306.47 | 6,462.05 | 7,493.29 | 13,432.01 |
| Write-to-read samples | 1,000 | 1,000 | 1,000 | 10,000 |
| Median write-to-read latency (µs) | 133.90 | 134.40 | 134.35 | 134.30 |
| P95 write-to-read latency (µs) | 171.10 | 182.00 | 199.80 | 163.40 |
| P99 write-to-read latency (µs) | 202.30 | 362.20 | 285.50 | 250.20 |

### Interpretation and limitations

All four runs completed with successful writes and reads for every generated tick, zero failed writes, and the expected reported trade counts for their respective workloads.

The median write-to-read latency remained close to 134 µs across all four runs. However, throughput varied substantially across the 1,000-tick runs, and P95/P99 latency also varied. These observations do not establish the cause of the variation or a stable performance baseline.

The 10,000-tick run reported 13,432.01 ticks/s, with median, P95, and P99 write-to-read latency of 134.30 µs, 163.40 µs, and 250.20 µs, respectively. A single larger run is not sufficient to establish reproducibility.

**Measurement boundary:** The reported latency percentiles measure ring-buffer write-to-read time. They do not measure the complete per-tick path through matching-engine processing. Total elapsed time includes pipeline setup and shutdown. These results therefore do not establish that the complete pipeline meets the 50 µs end-to-end latency target.

The workload uses synthetic ticks rather than real exchange data. These measurements are local development observations and should be retained separately from the historical runs above.

### Recommended follow-up

- Repeat the 10,000-tick benchmark to assess reproducibility.
- Keep the matching-engine, ring-buffer write-to-read, and full end-to-end latency measurements distinct.
- Record any future results alongside the exact workload and benchmark configuration.
- Investigate throughput and tail-latency variability before making stronger performance claims.