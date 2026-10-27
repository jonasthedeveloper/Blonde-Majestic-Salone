#!/usr/bin/env python3
"""Blonde Majestic Ladies Salon - web server (Python standard library only). Run:  python3 server.py

This file is only the development/standalone transport. All request handling — routing,
static files, uploads, auth, CSRF, cookies and error handling — lives in app/gateway.py so
exactly the same application can also be served by a WSGI host such as PythonAnywhere
(see wsgi_app.py) without running a second copy of any business logic.
"""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app import config, gateway


class Handler(BaseHTTPRequestHandler):
    server_version = "BlondeMajestic"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        if "--quiet" not in sys.argv:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % a))

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        head = self.command == "HEAD"
        body = b"" if length > gateway.MAX_BODY else (self.rfile.read(length) if length else b"")
        status, headers, out = gateway.handle(
            self.command, self.path, self.headers, body,
            ip=self.client_address[0], head=head, declared_length=length)
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        if out:
            self.wfile.write(out)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _handle


def main():
    gateway.start()
    srv = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    srv.daemon_threads = True
    print("Blonde Majestic Ladies Salon running at http://%s:%d  (Ctrl+C to stop)" % (
        "localhost" if config.HOST in ("127.0.0.1", "0.0.0.0") else config.HOST, config.PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()