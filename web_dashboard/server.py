
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

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
from web_dashboard.session_manager import SessionManager


DATA_DIR = ROOT / "data"
RING_PATH = DATA_DIR / f"web_dashboard_ring_buffer_{time.time_ns()}.bin"
LEDGER_PATH = DATA_DIR / f"web_dashboard_trades_{time.time_ns()}.db"

HOST = "0.0.0.0"
PORT = 5000

TICK_COUNT = 3000
TICK_INTERVAL_MS = 20.0
MAX_REQUEST_BODY = 16_384


class DashboardState:
    def __init__(self, dashboard: LiveDashboardState):
        self.dashboard = dashboard
        self.lock = threading.Lock()
        self.status = "starting"
        self.error = None
        self.metrics = None


def run_pipeline(state: DashboardState) -> None:
    try:
        with state.lock:
            state.status = "running"

        engine = state.dashboard.engine

        with TradeLedger(LEDGER_PATH) as ledger:
            with RingBuffer(
                RING_PATH,
                capacity=64,
                create=True,
            ) as ring:
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

            metrics = {
                "generated_ticks": result.metrics.generated_ticks,
                "successful_writes": result.metrics.successful_writes,
                "successful_reads": result.metrics.successful_reads,
                "matching_processed_records": (
                    result.metrics.matching_processed_records
                ),
                "persisted_trades": ledger.written,
            }

        with state.lock:
            state.metrics = metrics
            state.status = "completed"

    except Exception as exc:
        with state.lock:
            state.status = "error"
            state.error = str(exc)

        print(f"Pipeline error: {exc}")


def make_handler(
    state: DashboardState,
    session_manager: SessionManager,
):
    class Handler(BaseHTTPRequestHandler):

        def get_paper_exchange(self):
            exchange, session_id, is_new = (
                session_manager.get_exchange(
                    self.headers.get("Cookie")
                )
            )

            if is_new:
                forwarded_proto = self.headers.get(
                    "X-Forwarded-Proto", "http"
                ).lower()

                secure_flag = (
                    "; Secure" if forwarded_proto == "https" else ""
                )

                self.new_session_cookie = (
                    f"{SessionManager.COOKIE_NAME}={session_id}; "
                    "Path=/; HttpOnly; SameSite=Strict; "
                    f"Max-Age={session_manager.session_ttl_seconds}"
                    f"{secure_flag}"
                )

            return exchange

        def send_session_cookie(self):
            if hasattr(self, "new_session_cookie"):
                self.send_header(
                    "Set-Cookie",
                    self.new_session_cookie,
                )

        def send_json(self, payload, status_code=200):
            content = json.dumps(payload).encode("utf-8")

            self.send_response(status_code)
            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(len(content)),
            )
            self.send_header("Cache-Control", "no-store")
            self.send_session_cookie()
            self.end_headers()
            self.wfile.write(content)

        def validate_request_origin(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "").strip().lower()
            forwarded_proto = self.headers.get(
                "X-Forwarded-Proto", "http"
            ).strip().lower()

            if not origin or not host:
                return False

            if forwarded_proto not in {"http", "https"}:
                return False

            try:
                parsed_origin = urlparse(origin)

                if (
                    parsed_origin.username is not None
                    or parsed_origin.password is not None
                    or parsed_origin.path not in ("", "/")
                    or parsed_origin.params
                    or parsed_origin.query
                    or parsed_origin.fragment
                ):
                    return False

                return (
                    parsed_origin.scheme.lower() == forwarded_proto
                    and parsed_origin.netloc.lower() == host
                )

            except ValueError:
                return False

        def read_json_body(self):
            content_length = self.headers.get("Content-Length")

            if content_length is None:
                raise ValueError(
                    "Content-Length header is required."
                )

            try:
                length = int(content_length)
            except ValueError:
                raise ValueError(
                    "Invalid Content-Length header."
                ) from None

            if length <= 0:
                raise ValueError("Request body cannot be empty.")

            if length > MAX_REQUEST_BODY:
                raise ValueError("Request body is too large.")

            content_type = self.headers.get("Content-Type", "")

            if "application/json" not in content_type.lower():
                raise ValueError(
                    "Content-Type must be application/json."
                )

            raw_body = self.rfile.read(length)

            try:
                payload = json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValueError(
                    "Request body must contain valid JSON."
                ) from None

            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object.")

            return payload

        def do_GET(self):
            path = urlparse(self.path).path

            if path == "/healthz":
                self.send_json({"status": "ok"})
                return

            try:
                paper_exchange = self.get_paper_exchange()
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)
                return

            if path == "/":
                dashboard_path = (
                    Path(__file__).resolve().parent
                    / "recovered_dashboard.html"
                )

                try:
                    content = dashboard_path.read_bytes()
                except OSError:
                    self.send_json(
                        {"error": "Dashboard page is unavailable."},
                        500,
                    )
                    return

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(content)),
                )
                self.send_header("Cache-Control", "no-store")
                self.send_session_cookie()
                self.end_headers()
                self.wfile.write(content)
                return

            if path == "/api/snapshot":
                snapshot = state.dashboard.snapshot()
                snapshot["trade_count"] = (
                    state.dashboard.trade_count
                )

                with state.lock:
                    snapshot["status"] = state.status
                    snapshot["error"] = state.error
                    snapshot["metrics"] = state.metrics

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
                self.send_json(
                    paper_exchange.get_account_snapshot()
                )
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

            # Reject cross-origin or missing-origin requests before
            # creating a session or processing a paper-trading action.
            if not self.validate_request_origin():
                self.send_json(
                    {"error": "Request origin not allowed."},
                    403,
                )
                return

            try:
                paper_exchange = self.get_paper_exchange()
                payload = self.read_json_body()

                if path == "/api/orders/cancel":
                    if "order_id" not in payload:
                        raise ValueError(
                            "Missing required field: order_id."
                        )

                    result = paper_exchange.cancel_order(
                        payload["order_id"]
                    )

                    self.send_json({
                        "message": "Paper order cancelled.",
                        "result": result,
                    })
                    return

                if path != "/api/orders":
                    self.send_json(
                        {"error": "Not found."},
                        404,
                    )
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

            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, 503)

            except Exception:
                self.send_json(
                    {
                        "error": (
                            "The paper order could not be processed."
                        )
                    },
                    500,
                )

        def log_message(self, format, *args):
            pass

    return Handler


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    engine = MatchingEngine()
    latency_monitor = LatencyMonitor()
    dashboard = LiveDashboardState(
        engine,
        latency_monitor,
    )
    state = DashboardState(dashboard)

    # Each browser session receives its own PaperExchange.
    session_manager = SessionManager(
        session_ttl_seconds=12 * 60 * 60,
        max_sessions=50,
    )

    worker = threading.Thread(
        target=run_pipeline,
        args=(state,),
        name="chronosmatch-pipeline",
        daemon=True,
    )
    worker.start()

    # Render supplies the PORT environment variable.
    host = os.environ.get("HOST", HOST)
    port = int(os.environ.get("PORT", str(PORT)))

    server = ThreadingHTTPServer(
        (host, port),
        make_handler(state, session_manager),
    )

    print()
    print("ChronosMatch browser dashboard is running.")
    print(f"Listening on: {host}:{port}")
    print(f"Demo workload: {TICK_COUNT} ticks")
    print("Paper markets: BTC-SIM, ETH-SIM, SOL-SIM")
    print("Each browser session has an isolated paper account.")
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
