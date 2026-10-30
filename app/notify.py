"""In-app notifications + optional SMS (Twilio via env vars) + SMTP email.

Never raises: booking works with SMS off, and password reset degrades safely when
SMTP is not configured. Message bodies and tokens are never written to any log.
"""
import threading, json, base64, urllib.request, urllib.parse, urllib.error, re, smtplib, ssl
from email.message import EmailMessage
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


# ---------------- email (SMTP) ----------------
def email_ready():
    """True when an SMTP server is configured through the environment."""
    return bool(config.SMTP_HOST and config.SMTP_FROM)


def _send_email(to, subject, text_body, html_body):
    """Send one message. Returns (ok, detail); detail never contains the message body."""
    if not email_ready():
        return False, "smtp-not-configured"
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    try:
        if config.SMTP_USE_TLS:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                if config.SMTP_USERNAME:
                    s.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT) as s:
                if config.SMTP_USERNAME:
                    s.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                s.send_message(msg)
        return True, "sent"
    except Exception as e:
        # Type only - never the server response, credentials or the message itself.
        return False, type(e).__name__


def _reset_email_html(name, url, minutes, business):
    return f"""<!doctype html><html><body style="margin:0;padding:24px;background:#f6f1e9;font-family:Georgia,'Times New Roman',serif;color:#2A1A2B">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#fffdf9;border:1px solid #e8ddc9;border-radius:14px">
<tr><td style="padding:30px 32px 8px">
<div style="font:600 1.35rem Georgia,serif;color:#2A1A2B">{business}</div>
<div style="font:400 .78rem Arial,Helvetica,sans-serif;letter-spacing:.14em;color:#B08B4F;text-transform:uppercase;margin-top:4px">Ladies Salon</div>
<h1 style="font:600 1.6rem Georgia,serif;margin:26px 0 10px">Reset your password</h1>
<p style="font:400 1rem/1.6 Arial,Helvetica,sans-serif;color:#4a4a4a;margin:0 0 16px">Hello {name},</p>
<p style="font:400 1rem/1.6 Arial,Helvetica,sans-serif;color:#4a4a4a;margin:0 0 22px">We received a request to reset the password for your account. Press the button below to choose a new one.</p>
<p style="margin:0 0 24px"><a href="{url}" style="display:inline-block;background:#B08B4F;color:#fff;text-decoration:none;font:600 .95rem Arial,Helvetica,sans-serif;padding:13px 26px;border-radius:999px">Reset password</a></p>
<p style="font:400 .9rem/1.6 Arial,Helvetica,sans-serif;color:#6b6b6b;margin:0 0 8px">This link can be used once and expires in {minutes} minutes. If the button does not work, copy this link into your browser:</p>
<p style="font:400 .85rem/1.5 Arial,Helvetica,sans-serif;color:#7a5f9b;word-break:break-all;margin:0 0 22px">{url}</p>
<p style="font:400 .85rem/1.6 Arial,Helvetica,sans-serif;color:#8a8a8a;margin:0">If you did not request this, you can safely ignore this email - your password will stay unchanged. Never share this link with anyone.</p>
</td></tr></table></body></html>"""


def send_password_reset(to_email, user_name, url, minutes):
    """Email a password-reset link. Returns (ok, detail); never raises, never logs the link."""
    business = db.setting("business_name", "Blonde Majestic Ladies Salon")
    text_body = ("Reset your password\n\n"
                 "Hello %s,\n\n"
                 "We received a request to reset the password for your account.\n"
                 "Open this link to choose a new password (valid for %d minutes, one use only):\n\n"
                 "%s\n\n"
                 "If you did not request this, ignore this email - your password stays unchanged.\n"
                 "Never share this link with anyone.\n\n"
                 "- %s\n") % (user_name, minutes, url, business)
    return _send_email(to_email, "Reset your password - %s" % business, text_body,
                       _reset_email_html(user_name, url, minutes, business))


def notify_appointment(appt, ntype, title, body):
    """Notify the customer in-app (if registered) and by SMS (if configured)."""
    try:
        notify(appt.get("user_id"), ntype, title, body, "#/account/appointments")
        sms(appt.get("customer_phone"), "%s: %s" % (db.setting("business_name"), body))
    except Exception:
        pass
