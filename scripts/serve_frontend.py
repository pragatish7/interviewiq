"""Serve the prebuilt frontend (frontend/dist) and proxy /api to the backend.

Useful on machines without Node.js: builds are served straight from disk while
API calls are forwarded to the FastAPI backend.

Usage:
    python scripts/serve_frontend.py [port] [--api http://127.0.0.1:8000]
"""
import argparse
import http.client
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "host"}


def proxy(handler: BaseHTTPRequestHandler, api_base: str) -> None:
    """Forward the current request to the backend and stream the reply back."""
    target = api_base.split("://", 1)[1]
    host, _, port = target.partition(":")
    conn = http.client.HTTPConnection(host, int(port or 80), timeout=600)

    length = int(handler.headers.get("Content-Length") or 0)
    body = handler.rfile.read(length) if length else None

    headers = {k: v for k, v in handler.headers.items() if k.lower() not in HOP_BY_HOP}
    try:
        conn.request(handler.command, handler.path, body=body, headers=headers)
        resp = conn.getresponse()
    except OSError as exc:
        handler.send_error(502, f"Backend unreachable: {exc}")
        return

    handler.send_response(resp.status)
    for key, value in resp.getheaders():
        if key.lower() not in HOP_BY_HOP:
            handler.send_header(key, value)
    handler.end_headers()

    while True:
        chunk = resp.read(64 * 1024)
        if not chunk:
            break
        handler.wfile.write(chunk)
    conn.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    api_base = "http://127.0.0.1:8000"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _dispatch(self):
        if self.path.startswith("/api"):
            proxy(self, self.api_base)
            return
        path = self.path.split("?", 1)[0]
        candidate = os.path.normpath(os.path.join(DIST, path.lstrip("/")))
        if not candidate.startswith(DIST):
            self.send_error(403)
            return
        if not os.path.isfile(candidate):
            candidate = os.path.join(DIST, "index.html")  # SPA fallback
        if not os.path.isfile(candidate):
            self.send_error(404, "Run `npm run build` in frontend/ first")
            return
        self._send_file(candidate)

    def _send_file(self, path):
        with open(path, "rb") as fh:
            data = fh.read()
        import mimetypes

        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = lambda self: self._dispatch()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", nargs="?", type=int, default=3001)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    Handler.api_base = args.api
    if not os.path.isdir(DIST):
        sys.exit(f"No build found at {DIST}. Run `npm run build` in frontend/ first.")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving {DIST} at http://{args.host}:{args.port} (API -> {args.api})")
    server.serve_forever()


if __name__ == "__main__":
    main()
