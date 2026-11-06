from __future__ import annotations

import secrets
import threading
import time
from http.cookies import SimpleCookie

from web_dashboard.paper_exchange import PaperExchange


class SessionManager:
    """Maintain isolated paper-trading exchanges for browser sessions."""

    COOKIE_NAME = "chronosmatch_session"

    def __init__(
        self,
        session_ttl_seconds: int = 12 * 60 * 60,
        max_sessions: int = 50,
    ):
        if session_ttl_seconds <= 0 or max_sessions <= 0:
            raise ValueError("Session limits must be positive.")

        self.session_ttl_seconds = session_ttl_seconds
        self.max_sessions = max_sessions
        self.lock = threading.RLock()
        self.sessions = {}

    def _remove_expired(self, now: float) -> None:
        expired = [
            session_id
            for session_id, entry in self.sessions.items()
            if now - entry["last_seen"] >= self.session_ttl_seconds
        ]

        for session_id in expired:
            del self.sessions[session_id]

    def get_exchange(self, cookie_header: str | None = None):
        """Return (exchange, session_id, is_new_session)."""

        session_id = None

        if cookie_header:
            try:
                cookies = SimpleCookie()
                cookies.load(cookie_header)
                morsel = cookies.get(self.COOKIE_NAME)

                if morsel:
                    session_id = morsel.value
            except Exception:
                session_id = None

        now = time.monotonic()

        with self.lock:
            self._remove_expired(now)

            if session_id in self.sessions:
                entry = self.sessions[session_id]
                entry["last_seen"] = now
                return entry["exchange"], session_id, False

            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("The demo is temporarily at session capacity.")

            session_id = secrets.token_urlsafe(32)

            exchange = PaperExchange()

            self.sessions[session_id] = {
                "exchange": exchange,
                "last_seen": now,
            }

            return exchange, session_id, True