import hashlib, hmac, secrets, time, collections, threading, datetime as dt
from . import db, config

_lock = threading.Lock()
_hits = collections.defaultdict(collections.deque)


def hash_password(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$%s$%s" % (salt.hex(), h.hex())


def verify_password(pw, stored):
    try:
        _, salt, h = stored.split("$")
        cand = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(cand.hex(), h)
    except Exception:
        return False


def _th(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    exp = (dt.datetime.now() + dt.timedelta(days=config.SESSION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    db.run("INSERT INTO sessions VALUES(?,?,?,?)", (_th(token), user_id, exp, db.now_str()))
    return token


def user_for_token(token):
    if not token:
        return None
    return db.one("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1",
                  (_th(token), dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


def destroy_session(token):
    if token:
        db.run("DELETE FROM sessions WHERE token_hash=?", (_th(token),))


def rate_limited(key, limit, window):
    """True when `key` exceeded `limit` hits within `window` seconds."""
    now = time.time()
    with _lock:
        q = _hits[key]
        while q and q[0] < now - window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False
