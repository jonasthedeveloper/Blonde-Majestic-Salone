"""Transport-neutral request dispatch.

Everything that decides *what a request means* — routing, static files, uploads,
authentication, CSRF checks, cookies and error handling — lives here so that the exact
same logic can be served either by the built-in HTTP server (development, server.py)
or by a WSGI host such as PythonAnywhere (production, wsgi_app.py).
"""
import json
import mimetypes
import threading
import traceback
import urllib.parse

from . import booking, config, db, security, web
from . import api_public, api_admin  # noqa: F401  (registers routes)
from .web import ApiError, Req

MAX_BODY = 40 * 1024 * 1024
COOKIE = "bm_session"
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; "
       "frame-src https://www.openstreetmap.org https://www.google.com https://maps.google.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
SAFE_UPLOAD_EXT = {".jpg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}

_started = False
_start_lock = threading.Lock()


def start():
    """Idempotent boot: uploads directory, database schema/seed, reminder loop.

    Safe to call from every transport entry point and every worker process.
    """
    global _started
    if _started:
        return
    with _start_lock:
        if _started:
            return
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        db.init()
        threading.Thread(target=booking.reminder_loop, daemon=True).start()
        _started = True


def _respond(status, ctype, body, extras=(), head=False):
    """Assemble the response tuple (status, headers, body). HEAD gets headers only."""
    headers = [
        ("Content-Type", ctype),
        ("Content-Length", str(len(body))),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "same-origin"),
        ("X-Frame-Options", "DENY"),
        ("Content-Security-Policy", CSP),
    ]
    headers.extend(extras)
    return status, headers, (b"" if head else body)


def _json_response(status, data, extras=(), head=False):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return _respond(status, "application/json; charset=utf-8", body,
                    [("Cache-Control", "no-store")] + list(extras), head)


def _static(path, head):
    base = config.PUBLIC_DIR.resolve()
    f = (base / path.lstrip("/")).resolve()
    if base not in f.parents and f != base:
        return _json_response(404, {"error": "Not found"}, head=head)
    if not f.is_file():
        f = base / "index.html"  # single-page app fallback (hash routes)
    ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    return _respond(200, ctype, f.read_bytes(), [("Cache-Control", "no-cache")], head)


def _upload(name, head):
    f = (config.UPLOAD_DIR / urllib.parse.unquote(name)).resolve()
    if config.UPLOAD_DIR.resolve() not in f.parents or f.suffix.lower() not in SAFE_UPLOAD_EXT or not f.is_file():
        return _json_response(404, {"error": "Not found"}, head=head)
    return _respond(200, SAFE_UPLOAD_EXT[f.suffix.lower()], f.read_bytes(),
                    [("Cache-Control", "public, max-age=604800, immutable")], head)


def _api(method, path, query, headers, body, ip, head):
    if len(body) > MAX_BODY:
        raise ApiError(413, "That upload is too large.")
    req = Req(method, path, query, headers, body)
    req.ip = ip or headers.get("X-Real-IP") or ""
    cookie = req.cookies.get(COOKIE)
    token = cookie.value if cookie else None
    req.token = token
    req.user = security.user_for_token(token)
    handler, need = None, None
    allowed = False
    for rmethod, rx, fn, auth in web.ROUTES:
        mt = rx.match(path)
        if mt:
            allowed = True
            if rmethod == method:
                handler, req.params, need = fn, {k: (int(v) if v.isdigit() else v) for k, v in mt.groupdict().items()}, auth
                break
    if not handler:
        raise ApiError(405 if allowed else 404, "Not found.")
    if method not in ("GET", "HEAD"):  # CSRF defence: custom header + same-origin check
        if headers.get("X-Requested-With") != "fetch":
            raise ApiError(403, "Request blocked.")
        origin = headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).netloc != headers.get("Host"):
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
        return _respond(200, result["_ctype"], result["_raw"],
                        [("Content-Disposition", 'attachment; filename="%s"' % result["_filename"]),
                         ("Cache-Control", "no-store")], head)
    cookies = []
    if isinstance(result, dict):
        if "_set_cookie" in result:
            tok = result.pop("_set_cookie")
            cookies.append("%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d%s" % (
                COOKIE, tok, config.SESSION_DAYS * 86400, "; Secure" if config.SECURE_COOKIES else ""))
        if result.pop("_clear_cookie", False):
            cookies.append("%s=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" % COOKIE)
    return _json_response(200, result, [("Set-Cookie", c) for c in cookies], head)


def handle(method, raw_target, headers, body, ip="", head=False, declared_length=None):
    """Dispatch one request.

    method      e.g. GET / POST
    raw_target  full request target, e.g. "/api/services?q=x" (path + query)
    headers     mapping with .get(name) using canonical header names ("Content-Type", "Host", ...)
    body        request body bytes (already read by the transport)
    ip          client address, when the transport knows it
    head        True when the client asked for HEAD (headers only)
    declared_length  Content-Length as declared by the client, when the body was not read

    Returns (status, [(header, value), ...], body_bytes).
    """
    start()
    try:
        if (declared_length if declared_length is not None else len(body)) > MAX_BODY:
            raise ApiError(413, "That upload is too large.")
        parsed = urllib.parse.urlsplit(raw_target)
        path = parsed.path
        if not path.startswith("/api/"):
            if method not in ("GET", "HEAD"):
                return _json_response(405, {"error": "Method not allowed"}, head=head)
            if path.startswith("/uploads/"):
                return _upload(path[len("/uploads/"):], head)
            return _static(path, head)
        return _api(method, path, parsed.query, headers, body, ip, head)
    except ApiError as e:
        return _json_response(e.status, {"error": e.msg}, head=head)
    except Exception:
        traceback.print_exc()
        return _json_response(500, {"error": "Something went wrong on our side. Please try again."}, head=head)
