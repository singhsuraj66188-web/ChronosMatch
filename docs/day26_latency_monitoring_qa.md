# Day 26 - Latency Monitoring QA and Dashboard Validation

## 1. Scope

Reviewed latency monitoring, sample calculations, rolling-window behavior, dashboard snapshots, trade identification, and benchmark measurement boundaries.

This task covers QA testing and documentation only. No production implementation code was changed. Only QA tests and documentation were updated.

## 2. Files Reviewed

- monitoring/latency_monitor.py
- monitoring/live_dashboard.py
- monitoring/curses_dashboard.py
- simulator/ring_buffer_integration.py
- benchmarks/benchmark_e2e.py
- Related simulator, dashboard, integration, and renderer tests.

## 3. Latency Monitor Validation

The LatencyMonitor stores duration samples in nanoseconds using a bounded rolling window. The default capacity is 10,000 samples.

The summary provides:

| Metric | Description |
|---|---|
| count | Number of retained samples |
| median_us | Median latency in microseconds |
| p95_us | Nearest-rank 95th percentile |
| p99_us | Nearest-rank 99th percentile |
| max_us | Maximum retained latency |

Nanoseconds are converted to microseconds by dividing by 1,000. Empty summaries return zero values.

The maximum is calculated only from samples currently retained in the rolling window. Evicted samples no longer affect the result.

### Additional Tests

Two tests were added to tests/test_simulator.py:

1. test_latency_monitor_even_sample_median_and_unit_conversion
   - Validates median calculation for an even number of samples.
   - Checks nanosecond-to-microsecond conversion.
   - Checks P95, P99, and maximum values.

2. test_latency_monitor_max_excludes_evicted_sample
   - Validates rolling-window eviction.
   - Confirms that max_us uses only retained samples.

## 4. Latency Measurement Boundaries

The integration pipeline maintains three separate latency measurements.

1. Producer-start-to-consumer-read: Measures time from the producer starting a tick until the consumer reads it. Producer retries and backpressure can contribute.

2. Matching-processing: Measures the time spent inside process_record(). It excludes consumer waiting time.

3. Producer-start-to-matching-completion: Measures time from producer start until matching processing completes. It includes consumer waiting and matching processing.

These measurements have different timing boundaries and must not be compared as if they were the same metric.

When a dashboard state is supplied, its latency monitor is shared with the matching-processing monitor. Therefore, the dashboard displays matching-processing latency.

## 5. Dashboard Review

LiveDashboardState.snapshot() provides:

- The first eight bid levels.
- The first eight ask levels.
- The current latency summary.
- trades_per_s.
- The latest completed trade.

Trade records receive sequential trade_id values for each dashboard run. The latest trade contains buy and sell order IDs, price, quantity, and levels cleared.

Snapshot generation and trade publication use a re-entrant lock. The integration pipeline also uses this lock around matching and dashboard updates when a dashboard state is supplied.

This locking behavior was reviewed in the source code. No separate concurrent stress test was added.

The dashboard calculates trades_per_s using total trades divided by elapsed time since initialization. This is an average rate, not an instantaneous rate.

The terminal renderer displays median latency as P50, P99, and maximum latency. P95 is calculated by the monitor but is not displayed by the reviewed renderer.

## 6. Existing Test Coverage

Existing tests cover:

- Empty latency summaries.
- Negative and zero durations.
- P95 and P99 nearest-rank calculations.
- Invalid percentile values.
- Bounded sample windows.
- Invalid window sizes.
- Dashboard order-book and latency snapshots.
- Sequential trade IDs.
- Pipeline updates to the ledger and dashboard.
- Terminal rendering, spread, latency, and trade alerts.
- Integration sample counts and record reconciliation.
- A sustained 5,000-tick test using a ring-buffer capacity of eight.

The two additional tests strengthen coverage for even-sized median calculations and rolling-window maximum behavior.

## 7. Test Execution Results

Environment:
- Operating System: Windows
- Python: 3.14.8
- pytest: 9.1.1

Command executed:

python -m pytest tests/test_simulator.py tests/test_live_dashboard.py tests/test_live_pipeline_integration.py tests/test_curses_dashboard_render.py -v

Result:
- 46 tests passed.
- 0 failures.
- Execution time: 0.25 seconds.

This was a focused test run covering four test files. It was not a full repository test-suite run.

## 8. Limitations

- Benchmark source code was reviewed, but benchmark workloads were not rerun for this task.
- The benchmark uses synthetic ticks, not live exchange data.
- The three latency measurements have different boundaries and must be reported separately.
- Dashboard throughput is an average since initialization.
- Snapshot locking was reviewed, but no new concurrent stress test was added.
- P95 is available in the latency summary but is not displayed by the reviewed terminal renderer.
- Focused test results do not establish a full-suite result or prove a performance target.

## 9. Conclusion

The focused latency-monitoring, dashboard, pipeline-integration, and terminal-rendering tests passed successfully, with 46 tests passing in 0.25 seconds.

Two additional tests were introduced to validate even-sized median calculations, unit conversion, and rolling-window maximum behavior.

The review also documented the different latency measurement boundaries and dashboard throughput calculation to avoid misleading performance comparisons.

No implementation defects requiring code changes were identified during this review.