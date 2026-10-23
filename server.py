#!/usr/bin/env python3
"""Blonde Majestic Ladies Salon - web server (Python standard library only). Run:  python3 server.py"""
import json, mimetypes, sys, threading, traceback, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app import config, db, security, booking, web
from app import api_public, api_admin  # noqa: F401  (registers routes)
from app.web import ApiError, Req

MAX_BODY = 40 * 1024 * 1024
COOKIE = "bm_session"
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; "
       "frame-src https://www.openstreetmap.org https://www.google.com https://maps.google.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
SAFE_UPLOAD_EXT = {".jpg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}


class Handler(BaseHTTPRequestHandler):
    server_version = "BlondeMajestic"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        if "--quiet" not in sys.argv:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % a))

    def _send(self, status, body, ctype, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, data, cookies=None):
        self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                   [("Cache-Control", "no-store")] + [("Set-Cookie", c) for c in (cookies or [])])

    def _static(self, rel):
        base = config.PUBLIC_DIR.resolve()
        f = (base / rel.lstrip("/")).resolve()
        if base not in f.parents and f != base:
            return self._json(404, {"error": "Not found"})
        if not f.is_file():
            f = base / "index.html"  # single-page app fallback (hash routes)
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, f.read_bytes(), ctype, [("Cache-Control", "no-cache")])

    def _upload(self, name):
        f = (config.UPLOAD_DIR / urllib.parse.unquote(name)).resolve()
        if config.UPLOAD_DIR.resolve() not in f.parents or f.suffix.lower() not in SAFE_UPLOAD_EXT or not f.is_file():
            return self._json(404, {"error": "Not found"})
        self._send(200, f.read_bytes(), SAFE_UPLOAD_EXT[f.suffix.lower()], [("Cache-Control", "public, max-age=604800, immutable")])

    def _handle(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            if self.command not in ("GET", "HEAD"):
                return self._json(405, {"error": "Method not allowed"})
            if path.startswith("/uploads/"):
                return self._upload(path[len("/uploads/"):])
            return self._static("index.html" if path == "/" else path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "That upload is too large.")
            body = self.rfile.read(length) if length else b""
            req = Req(self.command, path, parsed.query, self.headers, body)
            req.ip = self.client_address[0]
            m = self.cookies_token(req)
            req.token = m
            req.user = security.user_for_token(m)
            handler = None
            allowed = False
            for method, rx, fn, auth in web.ROUTES:
                mt = rx.match(path)
                if mt:
                    allowed = True
                    if method == self.command:
                        handler, req.params, need = fn, {k: (int(v) if v.isdigit() else v) for k, v in mt.groupdict().items()}, auth
                        break
            if not handler:
                raise ApiError(405 if allowed else 404, "Not found.")
            if self.command not in ("GET", "HEAD"):  # CSRF defence: custom header + same-origin check
                if self.headers.get("X-Requested-With") != "fetch":
                    raise ApiError(403, "Request blocked.")
                origin = self.headers.get("Origin")
                if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
                    raise ApiError(403, "Request blocked.")
            if need:
                if not req.user:
                    raise ApiError(401, "Please sign in to continue.")
                if need == "admin" and req.user["role"] != "admin":
                    raise ApiError(403, "You do not have permission to do that.")
                if need == "staff" and req.user["role"] not in ("admin", "staff"):
                    raise ApiError(403, "You do not have permission to do that.")
            result = handler(req)
            if isinstance(result, dict) and "_raw" in result:
                return self._send(200, result["_raw"], result["_ctype"], [("Content-Disposition", 'attachment; filename="%s"' % result["_filename"]), ("Cache-Control", "no-store")])
            cookies = []
            if isinstance(result, dict):
                if "_set_cookie" in result:
                    tok = result.pop("_set_cookie")
                    cookies.append("%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d%s" % (COOKIE, tok, config.SESSION_DAYS * 86400, "; Secure" if config.SECURE_COOKIES else ""))
                if result.pop("_clear_cookie", False):
                    cookies.append("%s=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" % COOKIE)
            self._json(200, result, cookies)
        except ApiError as e:
            self._json(e.status, {"error": e.msg})
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "Something went wrong on our side. Please try again."})

    @staticmethod
    def cookies_token(req):
        c = req.cookies.get(COOKIE)
        return c.value if c else None

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _handle


def main():
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init()
    threading.Thread(target=booking.reminder_loop, daemon=True).start()
    srv = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    srv.daemon_threads = True
    print("Blonde Majestic Ladies Salon running at http://%s:%d  (Ctrl+C to stop)" % ("localhost" if config.HOST in ("127.0.0.1", "0.0.0.0") else config.HOST, config.PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
