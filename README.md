# ChronosMatch

**A simulated low-latency trading engine exploring Cython, shared-memory IPC, and price-time-priority matching.**

ChronosMatch is an educational FinTech engineering project focused on the design and measurement of a simulated high-frequency trading system. It explores how Python, Cython, memory-mapped shared memory, and asynchronous market-data generation can work together.

> **Status:** Early development. The shared-memory IPC, Cython integration, and end-to-end performance targets are still planned work.

## Objectives

- Build a limit order book with price-time priority.
- Explore a Cython-accelerated matching engine.
- Exchange fixed-size market-data records through memory-mapped shared memory.
- Generate simulated market events asynchronously.
- Measure matching latency and end-to-end processing performance.
- Document test results, design decisions, and limitations.

## Current Implementation

- Python order model with validation.
- Price-time-sorted bid and ask books.
- Matching at the resting order's price.
- Partial fills and multiple-order matching.
- Automated unit tests.
- A local matching-engine microbenchmark.

## Technology Stack

- Python
- Cython
- C/C++ build tools
- `mmap` and `struct`
- `asyncio`
- `pytest`

## Project Structure

```text
ChronosMatch/
├── benchmarks/
│   └── benchmark_engine.py
├── cython_test/
│   ├── hello.pyx
│   ├── hello.c
│   └── setup.py
├── docs/
│   └── benchmark_results.md
├── src/
│   └── chronosmatch/
│       ├── __init__.py
│       ├── order.py
│       └── matching_engine.py
├── tests/
│   ├── test_matching_engine.py
│   └── test_orders.py
├── .gitignore
└── pyproject.toml
```

## Run Locally

Use a compatible Python installation and create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows Command Prompt:

```bat
.venv\Scripts\activate.bat
```

Install the test dependency:

```bash
python -m pip install pytest
```

Run the test suite:

```bash
python -m pytest -q
```

Run the benchmark from the project root on Windows Command Prompt:

```bat
set PYTHONPATH=src
python benchmarks\benchmark_engine.py
```

## Performance Measurement

The project includes a local microbenchmark for order submission against a growing order book. These measurements are workload- and machine-dependent; they are not end-to-end trading-system latency measurements.

The long-term engineering objective is to investigate a sub-50-microsecond latency target. This target has not yet been validated for the complete system.

See [`docs/benchmark_results.md`](docs/benchmark_results.md) for the recorded local results.

## Safety and Scope

This project uses simulated orders and market data for educational and performance-engineering purposes. It is not connected to a live exchange and is not intended to execute real financial trades.

## Roadmap

- [x] Implement the initial Python order model and matching engine.
- [x] Add unit tests and an initial benchmark.
- [ ] Implement the shared-memory ring buffer.
- [ ] Integrate a Cython matching-engine hot path.
- [ ] Add an asynchronous market-data simulator.
- [ ] Build a terminal latency monitor.
- [ ] Measure and document end-to-end latency.
- [ ] Prepare integration tests, technical documentation, and a demo.

## Contributors

Team members and responsibilities will be added after collaboration is set up.
