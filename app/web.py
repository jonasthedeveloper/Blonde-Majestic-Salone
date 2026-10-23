"""Tiny routing/request layer on top of http.server (standard library only)."""
import re, json, email.parser, email.policy, http.cookies, urllib.parse

ROUTES = []


class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


def route(method, path, auth=None):
    """auth: None (public) | 'user' | 'staff' (admin or staff) | 'admin'"""
    def sub(m):
        return "(?P<%s>%s)" % (m.group(2), r"\d+" if m.group(1) else r"[^/]+")
    rx = re.compile("^" + re.sub(r"<(?:(int):)?(\w+)>", sub, path) + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn, auth))
        return fn
    return deco


class Req:
    def __init__(self, method, path, query, headers, body):
        self.method, self.path, self.headers, self.body = method, path, headers, body
        self.query = {k: v[0] for k, v in urllib.parse.parse_qs(query, keep_blank_values=True).items()}
        self.params, self.user, self.token = {}, None, None
        self.cookies = http.cookies.SimpleCookie(headers.get("Cookie", ""))
        self._json, self._form = None, None
        self.ip = headers.get("X-Real-IP") or ""

    def json(self):
        if self._json is None:
            try:
                self._json = json.loads(self.body.decode("utf-8") or "{}")
            except Exception:
                raise ApiError(400, "Invalid request data.")
            if not isinstance(self._json, dict):
                raise ApiError(400, "Invalid request data.")
        return self._json

    def multipart(self):
        """Returns (fields, files) where files = [(field, filename, bytes)]"""
        if self._form is None:
            ct = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ct:
                raise ApiError(400, "Expected a file upload form.")
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                b"Content-Type: " + ct.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + self.body)
            fields, files = {}, []
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                fn = part.get_filename()
                data = part.get_payload(decode=True) or b""
                if fn is not None:
                    if data:
                        files.append((name, fn, data))
                else:
                    fields[name] = data.decode("utf-8", "replace")
            self._form = (fields, files)
        return self._form


# ---- validation helpers ----
def text(d, key, maxlen=200, required=False, label=None):
    v = d.get(key)
    v = "" if v is None else str(v).strip()
    if required and not v:
        raise ApiError(400, "%s is required." % (label or key.replace("_", " ").capitalize()))
    if len(v) > maxlen:
        raise ApiError(400, "%s is too long (max %d characters)." % (label or key.replace("_", " ").capitalize(), maxlen))
    return v


def number(d, key, required=False, minv=None, maxv=None, label=None):
    v = d.get(key)
    if v is None or v == "":
        if required:
            raise ApiError(400, "%s is required." % (label or key.replace("_", " ").capitalize()))
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ApiError(400, "%s must be a number." % (label or key.replace("_", " ").capitalize()))
    if v != v or v in (float("inf"), float("-inf")):
        raise ApiError(400, "%s must be a number." % (label or key))
    if minv is not None and v < minv:
        raise ApiError(400, "%s must be at least %s." % (label or key.replace("_", " ").capitalize(), minv))
    if maxv is not None and v > maxv:
        raise ApiError(400, "%s must be at most %s." % (label or key.replace("_", " ").capitalize(), maxv))
    return v


def flag(d, key, default=0):
    v = d.get(key, default)
    return 1 if v in (True, 1, "1", "true", "on", "yes") else 0


EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RX = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def valid_phone(p):
    digits = re.sub(r"\D", "", p or "")
    return 7 <= len(digits) <= 15 and re.fullmatch(r"[+\d\s()\-]+", p or "") is not None
