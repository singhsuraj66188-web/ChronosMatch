
from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from chronosmatch.matching_engine import MatchingEngine
from ipc.ring_buffer import RingBuffer
from monitoring.latency_monitor import LatencyMonitor
from monitoring.live_dashboard import LiveDashboardState
from monitoring.trade_ledger import TradeLedger
from simulator.market_simulator import generate_ticks
from simulator.ring_buffer_integration import transfer_ticks
from web_dashboard.paper_exchange import PaperExchange


DATA_DIR = ROOT / "data"
RING_PATH = DATA_DIR / "web_dashboard_ring_buffer.bin"
LEDGER_PATH = DATA_DIR / f"web_dashboard_trades_{time.time_ns()}.db"

HOST = "127.0.0.1"
PORT = 5000

TICK_COUNT = 3000
TICK_INTERVAL_MS = 20.0
MAX_REQUEST_BODY = 16_384


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChronosMatch | Live Dashboard</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0;
    padding: 28px;
    background: #0b1020;
    color: #e5e7eb;
    font-family: Arial, sans-serif;
}
header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 15px;
    margin-bottom: 25px;
}
h1 { margin: 0; font-size: 27px; }
.subtitle { color: #94a3b8; margin-top: 7px; }
.status {
    border: 1px solid #334155;
    border-radius: 20px;
    padding: 9px 15px;
    color: #38bdf8;
}
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
}
.card {
    background: #151e32;
    border: 1px solid #26344d;
    border-radius: 12px;
    padding: 20px;
}
.card h3 {
    margin: 0 0 15px;
    color: #94a3b8;
    font-size: 13px;
    font-weight: normal;
}
.value { font-size: 27px; font-weight: bold; }
.unit { color: #94a3b8; font-size: 12px; margin-top: 6px; }
.panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
}
table { width: 100%; border-collapse: collapse; }
th, td {
    padding: 10px 7px;
    text-align: right;
    border-bottom: 1px solid #26344d;
}
th { color: #94a3b8; font-size: 12px; }
td { font-size: 14px; }
th:first-child, td:first-child { text-align: left; }
.buy { color: #34d399; }
.sell { color: #fb7185; }
.muted { color: #94a3b8; }
.trade-details { line-height: 2; }
footer { color: #64748b; margin-top: 24px; font-size: 12px; }
@media(max-width: 600px) {
    body { padding: 15px; }
    h1 { font-size: 22px; }
}
</style>
</head>
<body>
<header>
    <div>
        <h1>ChronosMatch</h1>
        <div class="subtitle">Live matching engine and IPC monitoring</div>
    </div>
    <div class="status" id="status">Connecting...</div>
</header>

<section class="grid">
    <div class="card">
        <h3>Total matched trades</h3>
        <div class="value" id="tradeCount">0</div>
        <div class="unit">Executed trades</div>
    </div>
    <div class="card">
        <h3>Trade throughput</h3>
        <div class="value" id="tradeRate">0.00</div>
        <div class="unit">Trades per second</div>
    </div>
    <div class="card">
        <h3>Latency samples</h3>
        <div class="value" id="sampleCount">0</div>
        <div class="unit">Matching-engine measurements</div>
    </div>
    <div class="card">
        <h3>Matching latency P99</h3>
        <div class="value" id="p99">0.00</div>
        <div class="unit">Microseconds</div>
    </div>
</section>

<section class="grid">
    <div class="card">
        <h3>Median matching latency</h3>
        <div class="value" id="median">0.00</div>
        <div class="unit">Microseconds</div>
    </div>
    <div class="card">
        <h3>P95 matching latency</h3>
        <div class="value" id="p95">0.00</div>
        <div class="unit">Microseconds</div>
    </div>
    <div class="card">
        <h3>Maximum matching latency</h3>
        <div class="value" id="maximum">0.00</div>
        <div class="unit">Microseconds</div>
    </div>
</section>

<section class="panels">
    <div class="card">
        <h3 class="buy">BUY ORDER BOOK — TOP 8</h3>
        <table>
            <thead><tr><th>Price (ticks)</th><th>Quantity</th></tr></thead>
            <tbody id="bids"></tbody>
        </table>
    </div>
    <div class="card">
        <h3 class="sell">SELL ORDER BOOK — TOP 8</h3>
        <table>
            <thead><tr><th>Price (ticks)</th><th>Quantity</th></tr></thead>
            <tbody id="asks"></tbody>
        </table>
    </div>
    <div class="card">
        <h3>Latest executed trade</h3>
        <div id="lastTrade" class="trade-details muted">Waiting for trades...</div>
    </div>
</section>

<footer>
    ChronosMatch simulated market data · Local dashboard ·
    Matching latency is measured inside process_record(), not end-to-end latency.
    <span id="updated"></span>
</footer>

<script>
function number(value) {
    return Number(value || 0).toFixed(2);
}

function renderBook(elementId, rows) {
    const element = document.getElementById(elementId);

    if (!rows || rows.length === 0) {
        element.innerHTML = '<tr><td colspan="2" class="muted">No resting orders</td></tr>';
        return;
    }

    element.innerHTML = rows.map(row =>
        `<tr><td>${row[0]}</td><td>${row[1]}</td></tr>`
    ).join("");
}

async function refresh() {
    try {
        const response = await fetch("/api/snapshot", {cache: "no-store"});

        if (!response.ok) {
            throw new Error("Dashboard API returned " + response.status);
        }

        const data = await response.json();
        const latency = data.latency;

        document.getElementById("status").textContent =
            data.status.toUpperCase();

        document.getElementById("tradeCount").textContent =
            data.trade_count;

        document.getElementById("tradeRate").textContent =
            number(data.trades_per_s);

        document.getElementById("sampleCount").textContent =
            latency.count;

        document.getElementById("median").textContent =
            number(latency.median_us);

        document.getElementById("p95").textContent =
            number(latency.p95_us);

        document.getElementById("p99").textContent =
            number(latency.p99_us);

        document.getElementById("maximum").textContent =
            number(latency.max_us);

        renderBook("bids", data.bids);
        renderBook("asks", data.asks);

        if (data.last_trade) {
            const trade = data.last_trade;

            document.getElementById("lastTrade").innerHTML =
                `Trade ID: ${trade.trade_id}<br>` +
                `Price: ${trade.price_ticks} ticks<br>` +
                `Quantity: ${trade.quantity}<br>` +
                `Buy order: ${trade.buy_order_id}<br>` +
                `Sell order: ${trade.sell_order_id}`;
        }

        document.getElementById("updated").textContent =
            " · Updated " + new Date().toLocaleTimeString();

    } catch (error) {
        document.getElementById("status").textContent = "CONNECTION ERROR";
        console.error(error);
    }
}

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


class DashboardState:
    def __init__(self, dashboard: LiveDashboardState):
        self.dashboard = dashboard
        self.lock = threading.Lock()
        self.status = "starting"
        self.error = None
        self.metrics = None


def run_pipeline(state: DashboardState) -> None:
    try:
        state.status = "running"

        engine = state.dashboard.engine

        with TradeLedger(LEDGER_PATH) as ledger:
            with RingBuffer(RING_PATH, capacity=64, create=True) as ring:
                result = asyncio.run(
                    transfer_ticks(
                        generate_ticks(
                            count=TICK_COUNT,
                            interval_ms=TICK_INTERVAL_MS,
                            seed=7,
                        ),
                        ring,
                        engine=engine,
                        ledger=ledger,
                        dashboard_state=state.dashboard,
                    )
                )

            ledger.flush()

        with state.lock:
            state.metrics = {
                "generated_ticks": result.metrics.generated_ticks,
                "successful_writes": result.metrics.successful_writes,
                "successful_reads": result.metrics.successful_reads,
                "matching_processed_records": (
                    result.metrics.matching_processed_records
                ),
                "persisted_trades": ledger.written,
            }
            state.status = "completed"

    except Exception as exc:
        with state.lock:
            state.status = "error"
            state.error = str(exc)

        print(f"Pipeline error: {exc}")


def make_handler(
    state: DashboardState,
    paper_exchange: PaperExchange,
):
    class Handler(BaseHTTPRequestHandler):

        def send_json(self, payload, status_code=200):
            content = json.dumps(payload).encode("utf-8")

            self.send_response(status_code)
            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8",
            )
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def read_json_body(self):
            content_length = self.headers.get("Content-Length")

            if content_length is None:
                raise ValueError("Content-Length header is required.")

            try:
                length = int(content_length)
            except ValueError:
                raise ValueError("Invalid Content-Length header.") from None

            if length <= 0:
                raise ValueError("Request body cannot be empty.")

            if length > MAX_REQUEST_BODY:
                raise ValueError("Request body is too large.")

            content_type = self.headers.get("Content-Type", "")

            if "application/json" not in content_type.lower():
                raise ValueError("Content-Type must be application/json.")

            raw_body = self.rfile.read(length)

            try:
                payload = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValueError("Request body must contain valid JSON.") from None

            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object.")

            return payload

        def do_GET(self):
            path = urlparse(self.path).path

            if path == "/":
                content = (Path(__file__).resolve().parent / "recovered_dashboard.html").read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return

            if path == "/api/snapshot":
                snapshot = state.dashboard.snapshot()
                snapshot["trade_count"] = state.dashboard.trade_count

                with state.lock:
                    status = state.status
                    error = state.error
                    metrics = state.metrics

                snapshot["status"] = status
                snapshot["error"] = error
                snapshot["metrics"] = metrics

                self.send_json(snapshot)
                return

            if path == "/api/markets":
                markets = [
                    paper_exchange.get_market_snapshot(symbol)
                    for symbol in paper_exchange.MARKETS
                ]
                self.send_json({"markets": markets})
                return

            if path == "/api/account":
                self.send_json(paper_exchange.get_account_snapshot())
                return

            if path == "/api/orders":
                self.send_json({
                    "orders": paper_exchange.get_open_orders()
                })
                return

            if path == "/api/trades":
                self.send_json({
                    "trades": paper_exchange.get_recent_trades()
                })
                return

            self.send_json({"error": "Not found."}, 404)

        def do_POST(self):
            path = urlparse(self.path).path

            try:
                payload = self.read_json_body()

                # Cancel an existing paper order.
                if path == "/api/orders/cancel":
                    if "order_id" not in payload:
                        raise ValueError("Missing required field: order_id.")

                    result = paper_exchange.cancel_order(
                        payload["order_id"]
                    )

                    self.send_json({
                        "message": "Paper order cancelled.",
                        "result": result,
                    })
                    return

                # Submit a new paper order.
                if path != "/api/orders":
                    self.send_json({"error": "Not found."}, 404)
                    return

                required_fields = {
                    "symbol",
                    "side",
                    "price",
                    "quantity",
                }

                missing = required_fields - payload.keys()

                if missing:
                    raise ValueError(
                        "Missing required fields: "
                        + ", ".join(sorted(missing))
                    )

                result = paper_exchange.submit_limit_order(
                    symbol=payload["symbol"],
                    side=payload["side"],
                    price=payload["price"],
                    quantity=payload["quantity"],
                )

                self.send_json(
                    {
                        "message": "Paper order accepted.",
                        "result": result,
                    },
                    201,
                )

            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)

            except Exception:
                self.send_json(
                    {"error": "The paper order could not be processed."},
                    500,
                )

        def log_message(self, format, *args):
            pass

    return Handler


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    engine = MatchingEngine()
    latency_monitor = LatencyMonitor()
    dashboard = LiveDashboardState(engine, latency_monitor)
    state = DashboardState(dashboard)

    # Independent synthetic paper exchange.
    # It does not share the IPC pipeline's matching engine.
    paper_exchange = PaperExchange()

    worker = threading.Thread(
        target=run_pipeline,
        args=(state,),
        name="chronosmatch-pipeline",
        daemon=True,
    )
    worker.start()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        make_handler(state, paper_exchange),
    )

    print()
    print("ChronosMatch browser dashboard is running.")
    print(f"Open: http://{HOST}:{PORT}")
    print(f"Demo workload: {TICK_COUNT} ticks")
    print("Paper markets: BTC-SIM, ETH-SIM, SOL-SIM")
    print("Paper trading uses synthetic virtual funds only.")
    print("Press Ctrl+C to stop the web server.")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
