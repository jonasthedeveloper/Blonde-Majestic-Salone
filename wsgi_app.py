"""WSGI entry point for production hosting (PythonAnywhere or any other WSGI server).

PythonAnywhere's WSGI configuration file (Web tab -> "WSGI configuration file") should
contain only:

    import sys
    sys.path.insert(0, "/home/<username>/Blonde-Majestic-Salone")
    from wsgi_app import application

Everything else — routing, static files, uploads, auth, cookies — is shared with the
development server through app/gateway.py.
"""
import pathlib
import sys
from http.client import responses as HTTP_REASONS

_ROOT = pathlib.Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import gateway  # noqa: E402


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD") or "GET"
    path = environ.get("PATH_INFO") or "/"
    query = environ.get("QUERY_STRING") or ""
    target = path + ("?" + query if query else "")

    headers = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            headers[key[5:].replace("_", "-").title()] = value
    if environ.get("CONTENT_TYPE"):
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    if environ.get("HTTP_X_REAL_IP"):  # .title() would mangle the casing of this one
        headers["X-Real-IP"] = environ["HTTP_X_REAL_IP"]

    length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(length) if length > 0 else b""

    status, resp_headers, out = gateway.handle(
        method, target, headers, body,
        ip=environ.get("REMOTE_ADDR") or "",
        head=(method == "HEAD"),
        declared_length=length)
    start_response("%d %s" % (status, HTTP_REASONS.get(status, "OK")), resp_headers)
    return [out]