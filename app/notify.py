"""In-app notifications + optional SMS (Twilio via env vars). Never raises: booking works with SMS off."""
import threading, json, base64, urllib.request, urllib.parse, urllib.error, re
from . import db, config


def notify(user_id, ntype, title, body="", link=""):
    if user_id:
        db.run("INSERT INTO notifications(user_id,type,title,body,link,created) VALUES(?,?,?,?,?,?)",
               (user_id, ntype, title, body, link, db.now_str()))


def notify_admins(ntype, title, body="", link="", staff_ids=None, chat_only=False):
    q = "SELECT id FROM users WHERE active=1 AND (role='admin'"
    a = []
    if staff_ids:
        q += " OR (role='staff' AND staff_id IN (%s))" % ",".join("?" * len(staff_ids))
        a += list(staff_ids)
    if chat_only:
        q += " OR (role='staff' AND can_chat=1)"
    q += ")"
    for r in db.all(q, a):
        notify(r["id"], ntype, title, body, link)


def sms_ready():
    return bool(config.SMS_ENABLED and config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_FROM_NUMBER)


def to_e164(p):
    p = re.sub(r"[^\d+]", "", p or "")
    if p.startswith("00"):
        p = "+" + p[2:]
    if p.startswith("+"):
        return p
    cc = config.SMS_DEFAULT_COUNTRY_CODE
    if p.startswith("0"):
        return "+" + cc + p[1:]
    if len(p) == 9 and p.startswith("5"):
        return "+" + cc + p
    return "+" + p


def _send(to, body):
    try:
        url = "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % config.TWILIO_ACCOUNT_SID
        data = urllib.parse.urlencode({"To": to, "From": config.TWILIO_FROM_NUMBER, "Body": body}).encode()
        req = urllib.request.Request(url, data=data)
        tok = base64.b64encode(("%s:%s" % (config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)).encode()).decode()
        req.add_header("Authorization", "Basic " + tok)
        with urllib.request.urlopen(req, timeout=15) as r:
            status, detail = "sent", str(r.status)
    except urllib.error.HTTPError as e:
        status, detail = "failed", "HTTP %s" % e.code
    except Exception as e:
        status, detail = "failed", type(e).__name__
    try:
        db.run("INSERT INTO sms_log(to_number,body,status,detail,created) VALUES(?,?,?,?,?)", (to, body, status, detail, db.now_str()))
    except Exception:
        pass


def sms(phone, body):
    """Fire-and-forget. Returns False (and does nothing) when SMS is not configured."""
    if not sms_ready() or not phone:
        return False
    threading.Thread(target=_send, args=(to_e164(phone), body), daemon=True).start()
    return True


def notify_appointment(appt, ntype, title, body):
    """Notify the customer in-app (if registered) and by SMS (if configured)."""
    try:
        notify(appt.get("user_id"), ntype, title, body, "#/account/appointments")
        sms(appt.get("customer_phone"), "%s: %s" % (db.setting("business_name"), body))
    except Exception:
        pass
