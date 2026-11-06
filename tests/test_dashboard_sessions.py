
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from monitoring.latency_monitor import LatencyMonitor
from monitoring.live_dashboard import LiveDashboardState
from web_dashboard.server import DashboardState, make_handler
from web_dashboard.session_manager import SessionManager
from chronosmatch.matching_engine import MatchingEngine


def start_test_server():
    dashboard = LiveDashboardState(
    MatchingEngine(),
    LatencyMonitor(),
)

    state = DashboardState(dashboard)
    manager = SessionManager()

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(state, manager),
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    return server, thread


def request(server, method, path, cookie=None, body=None):
    host = f"127.0.0.1:{server.server_port}"

    connection = HTTPConnection(
        "127.0.0.1",
        server.server_port,
        timeout=5,
    )

    headers = {
        "Origin": f"http://{host}",
    }

    if cookie:
        headers["Cookie"] = cookie

    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body)

    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()

    result = {
        "status": response.status,
        "body": response.read(),
        "set_cookie": response.getheader("Set-Cookie"),
    }

    connection.close()
    return result


def request_with_origin(server, method, path, origin=None, body=None):
    connection = HTTPConnection(
        "127.0.0.1",
        server.server_port,
        timeout=5,
    )

    headers = {}

    if origin is not None:
        headers["Origin"] = origin

    if body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(body)

    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()

    result = {
        "status": response.status,
        "body": response.read(),
        "set_cookie": response.getheader("Set-Cookie"),
    }

    connection.close()
    return result


def test_health_check_does_not_create_a_session():
    server, _ = start_test_server()

    try:
        response = request(server, "GET", "/healthz")

        assert response["status"] == 200
        assert response["set_cookie"] is None
    finally:
        server.shutdown()
        server.server_close()


def test_browser_receives_and_reuses_session_cookie():
    server, _ = start_test_server()

    try:
        first = request(server, "GET", "/api/account")

        assert first["status"] == 200
        assert first["set_cookie"] is not None

        cookie = first["set_cookie"].split(";", 1)[0]

        second = request(
            server,
            "GET",
            "/api/account",
            cookie=cookie,
        )

        assert second["status"] == 200
        assert second["set_cookie"] is None
        assert json.loads(first["body"]) == json.loads(second["body"])
    finally:
        server.shutdown()
        server.server_close()


def test_two_http_visitors_receive_separate_accounts():
    server, _ = start_test_server()

    try:
        visitor_a = request(server, "GET", "/api/account")
        visitor_b = request(server, "GET", "/api/account")

        cookie_a = visitor_a["set_cookie"].split(";", 1)[0]
        cookie_b = visitor_b["set_cookie"].split(";", 1)[0]

        assert cookie_a != cookie_b

        account_a = json.loads(visitor_a["body"])
        account_b = json.loads(visitor_b["body"])

        assert account_a == account_b

        order = request(
            server,
            "POST",
            "/api/orders",
            cookie=cookie_a,
            body={
                "symbol": "BTC-SIM",
                "side": "BUY",
                "price": 6_499_500,
                "quantity": 1,
            },
        )

        assert order["status"] == 201

        orders_a = request(
            server,
            "GET",
            "/api/orders",
            cookie=cookie_a,
        )
        orders_b = request(
            server,
            "GET",
            "/api/orders",
            cookie=cookie_b,
        )

        assert len(json.loads(orders_a["body"])["orders"]) == 1
        assert json.loads(orders_b["body"])["orders"] == []
    finally:
        server.shutdown()
        server.server_close()


def test_cross_origin_post_is_rejected():
    server, _ = start_test_server()

    try:
        response = request_with_origin(
            server,
            "POST",
            "/api/orders",
            origin="https://evil.example",
            body={
                "symbol": "BTC-SIM",
                "side": "BUY",
                "price": 6_499_500,
                "quantity": 1,
            },
        )

        assert response["status"] == 403
        assert response["set_cookie"] is None
    finally:
        server.shutdown()
        server.server_close()


def test_post_without_origin_is_rejected():
    server, _ = start_test_server()

    try:
        response = request_with_origin(
            server,
            "POST",
            "/api/orders",
            body={
                "symbol": "BTC-SIM",
                "side": "BUY",
                "price": 6_499_500,
                "quantity": 1,
            },
        )

        assert response["status"] == 403
        assert response["set_cookie"] is None
    finally:
        server.shutdown()
        server.server_close()
