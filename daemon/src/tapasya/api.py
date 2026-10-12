"""Local HTTP API (stdlib only). Binds to 127.0.0.1.

POST /v1/tab    {domain, title, shorts, audible}  from the Brave extension (Origin must be chrome-extension://)
GET  /v1/status {day, goal_minutes, studied_minutes}  for the AI assistant (Phase 4 expands this)
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class TabState:
    """Latest tab info reported by the extension. Considered stale after `stale_seconds`."""

    def __init__(self, stale_seconds: float = 90) -> None:
        self.stale_seconds = stale_seconds
        self._lock = threading.Lock()
        self._data: dict | None = None

    def update(self, domain: str, title: str, shorts: bool, audible: bool = False, eligible: bool | None = None, now: float | None = None) -> None:
        # If explicitly marked ineligible (e.g., internal page), clear the state immediately.
        if eligible is False:
            with self._lock:
                self._data = None
            return
        # Ignore empty or whitespace-only domain reports without explicit eligible flag.
        # These come from focus loss (WINDOW_ID_NONE) where no report should have been sent,
        # but we defensively ignore them to preserve the last valid state.
        if not domain or not domain.strip():
            return
        # Valid domain - update state.
        with self._lock:
            self._data = {"domain": domain, "title": title, "shorts": shorts, "audible": audible,
                          "ts": time.monotonic() if now is None else now}

    def current(self, now: float | None = None) -> dict | None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._data and now - self._data["ts"] <= self.stale_seconds:
                return dict(self._data)
        return None


def make_server(state: TabState, host: str, port: int, status_fn=None) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the journal quiet
            pass

        def _origin_ok(self) -> bool:
            return (self.headers.get("Origin") or "").startswith("chrome-extension://")

        def _cors(self) -> None:
            origin = self.headers.get("Origin")
            if origin and origin.startswith("chrome-extension://"):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

        def _reply(self, code: int, body: dict | None = None) -> None:
            raw = json.dumps(body).encode() if body is not None else b""
            self.send_response(code)
            self._cors()
            if body is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self):
            self._reply(204 if self._origin_ok() else 403)

        def do_POST(self):
            if self.path != "/v1/tab":
                return self._reply(404)
            if not self._origin_ok():
                return self._reply(403, {"error": "extension origin required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 4096:
                    return self._reply(413)
                data = json.loads(self.rfile.read(length) or b"{}")
                domain = str(data.get("domain", ""))[:253]
                title = str(data.get("title", ""))[:200]
                shorts = bool(data.get("shorts", False))
                audible = bool(data.get("audible", False))
                # eligible is optional; None means not provided (backward compat)
                eligible = data.get("eligible", None)
                if isinstance(eligible, bool):
                    pass  # use as-is
                else:
                    eligible = None
            except (ValueError, TypeError):
                return self._reply(400)
            state.update(domain, title, shorts, audible, eligible)
            self._reply(204)

        def do_GET(self):
            if self.path == "/v1/status" and status_fn:
                return self._reply(200, status_fn())
            self._reply(404)

    return ThreadingHTTPServer((host, port), Handler)


def start_in_thread(server: ThreadingHTTPServer) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t
