"""Availability engine, double-booking prevention, booking / reschedule / cancel, promo discounts."""
import datetime as dt, json, secrets, threading
from . import db, config, notify
from .web import ApiError, text, valid_phone, EMAIL_RX, DATE_RX, TIME_RX

LOCK = threading.Lock()
ACTIVE = ("pending", "confirmed", "in_progress", "completed")
MAX_ITEMS = 6


def now_local():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=config.TZ_OFFSET)


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def mm(m):
    return "%02d:%02d" % (m // 60, m % 60)


def t12(s):
    h, m = hm(s) // 60, hm(s) % 60
    return "%d:%02d %s" % ((h % 12) or 12, m, "AM" if h < 12 else "PM")


def pretty(date_s, time_s):
    d = dt.date.fromisoformat(date_s)
    return "%s at %s" % (d.strftime("%a, %d %b %Y"), t12(time_s))


def parse_date(s):
    if not DATE_RX.match(s or ""):
        raise ApiError(400, "Please choose a valid date.")
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise ApiError(400, "Please choose a valid date.")


def salon_window(date):
    d = (db.setting("hours") or [])[date.weekday()]
    if not d or d.get("closed"):
        return None
    return hm(d["open"]), hm(d["close"])


class Day:
    """Everything that affects availability on one date, loaded once."""

    def __init__(self, date, exclude=None):
        self.date, self.ds = date, date.isoformat()
        self.win = salon_window(date)
        self.closed_reason = None if self.win else "The salon is closed on this day."
        self.busy = {}
        rows = db.all("SELECT i.staff_id,i.start_time,i.end_time FROM appointment_items i JOIN appointments a ON a.id=i.appointment_id "
                      "WHERE i.date=? AND a.status IN (%s) AND (? IS NULL OR a.id!=?)" % ",".join("?" * len(ACTIVE)),
                      (self.ds, *ACTIVE, exclude, exclude))
        for r in rows:
            self.busy.setdefault(r["staff_id"], []).append((hm(r["start_time"]), hm(r["end_time"])))
        self.blocks = db.all("SELECT * FROM blocks WHERE date_from<=? AND date_to>=?", (self.ds, self.ds))
        self.hours = {r["staff_id"]: r for r in db.all("SELECT * FROM staff_hours WHERE weekday=?", (date.weekday(),))}
        for b in self.blocks:
            if b["staff_id"] is None and not b["start_time"]:
                self.win, self.closed_reason = None, (b["reason"] or "The salon is unavailable on this date.")

    def free(self, sid, s, e):
        if not self.win:
            return False
        lo, hi = self.win
        h = self.hours.get(sid)
        if h:
            if h["off"]:
                return False
            lo, hi = max(lo, hm(h["start"])), min(hi, hm(h["end"]))
        if s < lo or e > hi:
            return False
        for b in self.blocks:
            if b["staff_id"] in (None, sid):
                if not b["start_time"]:
                    return False
                if s < hm(b["end_time"]) and hm(b["start_time"]) < e:
                    return False
        return not any(s < be and bs < e for bs, be in self.busy.get(sid, []))

    def load(self, sid):
        return len(self.busy.get(sid, []))


def service_context(items, date):
    out, seen = [], set()
    for it in items:
        try:
            sid = int(it.get("service_id"))
        except (TypeError, ValueError):
            raise ApiError(400, "Please select a valid service.")
        if sid in seen:
            continue
        seen.add(sid)
        s = db.one("SELECT s.*, c.active AS cat_active FROM services s JOIN categories c ON c.id=s.category_id WHERE s.id=?", (sid,))
        if not s or not s["active"] or not s["cat_active"]:
            raise ApiError(400, "One of the selected services is not available.")
        if date.weekday() not in json.loads(s["avail_days"] or "[0,1,2,3,4,5,6]"):
            raise ApiError(400, "%s is not offered on this day. Please choose another date." % s["name"])
        staff = [r["id"] for r in db.all("SELECT st.id FROM staff st JOIN staff_services ss ON ss.staff_id=st.id "
                                         "WHERE ss.service_id=? AND st.active=1 ORDER BY st.sort,st.id", (sid,))]
        pref = it.get("staff_id")
        if pref not in (None, "", 0, "0", "any"):
            try:
                pref = int(pref)
            except (TypeError, ValueError):
                raise ApiError(400, "Please select a valid stylist.")
            if pref not in staff:
                raise ApiError(400, "The selected stylist does not offer %s." % s["name"])
            cands = [pref]
        else:
            cands = staff
        if not cands:
            raise ApiError(400, "%s cannot be booked online yet. Please chat with the salon or call us." % s["name"])
        out.append({"svc": s, "cands": cands, "dur": int(s["duration_min"] or db.setting("default_duration", 60))})
    if not out:
        raise ApiError(400, "Please select at least one service.")
    if len(out) > MAX_ITEMS:
        raise ApiError(400, "You can book up to %d services at once." % MAX_ITEMS)
    return out


def chain(day, start, sc):
    t, picks = start, []
    for x in sc:
        e = t + x["dur"]
        opts = [c for c in x["cands"] if day.free(c, t, e)]
        if not opts:
            return None
        sid = min(opts, key=lambda c: (day.load(c), c))
        picks.append((x, sid, t, e))
        t = e
    return picks


def check_date(date, admin=False):
    now = now_local()
    if date < now.date():
        raise ApiError(400, "That date has already passed. Please choose today or a later date.")
    horizon = int(db.setting("booking_horizon_days", 60))
    if not admin and (date - now.date()).days > horizon:
        raise ApiError(400, "Bookings can be made up to %d days ahead." % horizon)


def available_slots(date, items, exclude=None, admin=False):
    check_date(date, admin)
    sc = service_context(items, date)
    day = Day(date, exclude)
    if not day.win:
        return {"closed": True, "reason": day.closed_reason, "slots": []}
    step = max(5, int(db.setting("slot_step", 30)))
    total = sum(x["dur"] for x in sc)
    now = now_local()
    min_t = (now.hour * 60 + now.minute + int(db.setting("min_notice_minutes", 0))) if date == now.date() else -1
    slots = []
    for start in range(day.win[0], day.win[1] - total + 1, step):
        if start < min_t:
            continue
        p = chain(day, start, sc)
        if p:
            slots.append({"time": mm(start), "label": t12(mm(start)), "staff": [q[1] for q in p]})
    return {"closed": False, "slots": slots, "duration": total}


def promo_discount(promo, rows):
    """rows: [{service_id, price}]. Returns discount amount (never more than the base)."""
    if not promo:
        return 0.0
    ids = json.loads(promo.get("service_ids") or "[]")
    match = [r for r in rows if not ids or r["service_id"] in ids]
    if ids and promo["requires_all"] and not all(i in [r["service_id"] for r in rows] for i in ids):
        return 0.0
    base = sum(r["price"] or 0 for r in match)
    if base <= 0:
        return 0.0
    d = base * promo["discount_value"] / 100 if promo["discount_type"] == "percent" else min(promo["discount_value"], base)
    return round(min(d, base), 2)


def promo_applicable(promo, service_ids, date_s):
    if not promo or not promo["active"]:
        return False
    if promo["start_date"] and date_s < promo["start_date"]:
        return False
    if promo["end_date"] and date_s > promo["end_date"]:
        return False
    ids = json.loads(promo.get("service_ids") or "[]")
    if not ids:
        return True
    return all(i in service_ids for i in ids) if promo["requires_all"] else any(i in service_ids for i in ids)


def _ref():
    return "BM-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


def appt_detail(a):
    a["items"] = db.all("SELECT i.*, st.name AS staff_name FROM appointment_items i LEFT JOIN staff st ON st.id=i.staff_id WHERE appointment_id=? ORDER BY start_time", (a["id"],))
    a["payment"] = db.one("SELECT * FROM payments WHERE appointment_id=?", (a["id"],))
    if a.get("promo_id"):
        a["promo_title"] = db.scalar("SELECT title FROM promotions WHERE id=?", (a["promo_id"],))
    a["estimated_total"] = None if any(i["price"] is None for i in a["items"]) else round(sum(i["price"] for i in a["items"]), 2)
    return a


def create_booking(d, user=None, admin=False):
    name = text(d, "customer_name", 80, True, "Your name")
    phone = text(d, "customer_phone", 25, True, "Phone number")
    mail = text(d, "customer_email", 120).lower()
    if len(name) < 2:
        raise ApiError(400, "Please enter your full name.")
    if not valid_phone(phone):
        raise ApiError(400, "Please enter a valid phone number.")
    if mail and not EMAIL_RX.match(mail):
        raise ApiError(400, "Please enter a valid email address.")
    notes = text(d, "customer_notes", 500)
    date = parse_date(d.get("date"))
    tm = d.get("time") or ""
    if not TIME_RX.match(tm):
        raise ApiError(400, "Please choose a time.")
    items = d.get("items")
    if not isinstance(items, list):
        raise ApiError(400, "Please select at least one service.")
    check_date(date, admin)
    sc = service_context(items, date)
    promo = None
    if d.get("promo_id"):
        promo = db.one("SELECT * FROM promotions WHERE id=?", (d.get("promo_id"),))
        if not promo_applicable(promo, [x["svc"]["id"] for x in sc], date.isoformat()):
            raise ApiError(400, "That promotion is not valid for this booking.")
    with LOCK:
        day = Day(date)
        if not day.win:
            raise ApiError(409, day.closed_reason)
        start = hm(tm)
        now = now_local()
        if date == now.date() and start < now.hour * 60 + now.minute + int(db.setting("min_notice_minutes", 0)):
            raise ApiError(400, "That time has already passed. Please choose a later time.")
        step = max(5, int(db.setting("slot_step", 30)))
        if (start - day.win[0]) % step:
            raise ApiError(400, "Please choose one of the listed times.")
        picks = chain(day, start, sc)
        if not picks:
            raise ApiError(409, "Sorry, that time is no longer available. Please choose another time.")
        status = "confirmed" if (admin and d.get("status") == "confirmed") or db.setting("auto_confirm") else "pending"
        with db.tx():
            now_s = db.now_str()
            aid = db.run("INSERT INTO appointments(ref,user_id,customer_name,customer_phone,customer_email,date,start_time,end_time,status,customer_notes,promo_id,source,created,updated) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (_ref(), user["id"] if user and user["role"] == "customer" else None, name, phone, mail, date.isoformat(), mm(picks[0][2]), mm(picks[-1][3]),
                          status, notes, promo["id"] if promo else None, "admin" if admin else "online", now_s, now_s))
            for x, sid, s, e in picks:
                db.run("INSERT INTO appointment_items(appointment_id,service_id,service_name,category_id,staff_id,date,start_time,end_time,price) VALUES(?,?,?,?,?,?,?,?,?)",
                       (aid, x["svc"]["id"], x["svc"]["name"], x["svc"]["category_id"], sid, date.isoformat(), mm(s), mm(e), x["svc"]["price"]))
    a = appt_detail(db.one("SELECT * FROM appointments WHERE id=?", (aid,)))
    when = pretty(a["date"], a["start_time"])
    svc_names = ", ".join(i["service_name"] for i in a["items"])
    verb = "confirmed" if status == "confirmed" else "received (awaiting salon confirmation)"
    notify.notify_appointment(a, "booking", "Booking " + ("confirmed" if status == "confirmed" else "received"),
                              "Your booking %s for %s on %s was %s." % (a["ref"], svc_names, when, verb))
    notify.notify_admins("booking", "New booking %s" % a["ref"], "%s - %s on %s" % (name, svc_names, when), "#/admin/appointments",
                         staff_ids=[i["staff_id"] for i in a["items"] if i["staff_id"]])
    return a


def reschedule(a, date_s, time_s, admin=False):
    if a["status"] not in ("pending", "confirmed"):
        raise ApiError(400, "This appointment can no longer be changed.")
    date = parse_date(date_s)
    if not TIME_RX.match(time_s or ""):
        raise ApiError(400, "Please choose a time.")
    check_date(date, admin)
    items = db.all("SELECT * FROM appointment_items WHERE appointment_id=? ORDER BY start_time", (a["id"],))
    sc = service_context([{"service_id": i["service_id"], "staff_id": i["staff_id"]} for i in items if i["service_id"]], date)
    with LOCK:
        day = Day(date, exclude=a["id"])
        if not day.win:
            raise ApiError(409, day.closed_reason)
        now = now_local()
        start = hm(time_s)
        if date == now.date() and start < now.hour * 60 + now.minute:
            raise ApiError(400, "That time has already passed.")
        picks = chain(day, start, sc)
        if not picks:
            raise ApiError(409, "Sorry, that time is not available. Please choose another time.")
        with db.tx():
            by_service = {x["svc"]["id"]: (sid, s, e) for x, sid, s, e in picks}
            for i in items:
                sid, s, e = by_service[i["service_id"]]
                db.run("UPDATE appointment_items SET staff_id=?,date=?,start_time=?,end_time=? WHERE id=?", (sid, date_s, mm(s), mm(e), i["id"]))
            status = a["status"] if (admin or db.setting("auto_confirm")) else "pending"
            db.run("UPDATE appointments SET date=?,start_time=?,end_time=?,status=?,reminded=0,updated=? WHERE id=?",
                   (date_s, mm(picks[0][2]), mm(picks[-1][3]), status, db.now_str(), a["id"]))
    a2 = db.one("SELECT * FROM appointments WHERE id=?", (a["id"],))
    when = pretty(a2["date"], a2["start_time"])
    notify.notify_appointment(a2, "booking_change", "Booking changed", "Your booking %s was moved to %s." % (a2["ref"], when))
    if not admin:
        notify.notify_admins("booking_change", "Booking rescheduled %s" % a2["ref"], "%s moved to %s" % (a2["customer_name"], when), "#/admin/appointments")
    return appt_detail(a2)


def cancel(a, by_admin=False, reason=""):
    if a["status"] not in ("pending", "confirmed"):
        raise ApiError(400, "This appointment can no longer be cancelled.")
    if not by_admin:
        cutoff = float(db.setting("customer_change_cutoff_hours", 0) or 0)
        start = dt.datetime.fromisoformat(a["date"] + "T" + a["start_time"])
        if cutoff and (start - now_local()).total_seconds() < cutoff * 3600:
            raise ApiError(400, "Appointments can only be changed or cancelled at least %g hours before the start time. Please contact the salon." % cutoff)
    db.run("UPDATE appointments SET status='cancelled',updated=? WHERE id=?", (db.now_str(), a["id"]))
    msg = "Your booking %s on %s was cancelled." % (a["ref"], pretty(a["date"], a["start_time"]))
    if reason:
        msg += " Reason: " + reason
    notify.notify_appointment(a, "booking_cancel", "Booking cancelled", msg)
    if not by_admin:
        notify.notify_admins("booking_cancel", "Booking cancelled %s" % a["ref"], "%s cancelled %s" % (a["customer_name"], pretty(a["date"], a["start_time"])), "#/admin/appointments")


def reminder_loop():
    import time
    while True:
        try:
            now = now_local()
            limit = now + dt.timedelta(hours=config.REMINDER_HOURS)
            for a in db.all("SELECT * FROM appointments WHERE status='confirmed' AND reminded=0 AND date>=? AND date<=?", (now.strftime("%Y-%m-%d"), limit.strftime("%Y-%m-%d"))):
                start = dt.datetime.fromisoformat(a["date"] + "T" + a["start_time"])
                if now <= start <= limit:
                    db.run("UPDATE appointments SET reminded=1 WHERE id=?", (a["id"],))
                    notify.notify_appointment(a, "reminder", "Appointment reminder", "Reminder: your appointment %s is on %s." % (a["ref"], pretty(a["date"], a["start_time"])))
        except Exception as e:  # keep the loop alive
            print("reminder loop error:", e)
        time.sleep(60)
