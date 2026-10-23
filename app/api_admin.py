"""Admin / staff endpoints. Every route here declares auth='admin' or 'staff'; the server enforces it before the handler runs."""
import json, re, sqlite3, datetime as dt
from . import db, security, booking, notify, uploads, revenue
from .api_public import rating_summary, conversation_for
from .web import route, ApiError, text, number, flag, EMAIL_RX, DATE_RX, TIME_RX, valid_phone

IMG_RX = re.compile(r"^[0-9a-f]{24}\.(jpg|png|gif|webp)$")


def img(d, key="image"):
    v = text(d, key, 60)
    if v and not IMG_RX.match(v):
        raise ApiError(400, "Invalid image reference.")
    return v


def datev(d, key, required=False):
    v = text(d, key, 10, required)
    if v and not DATE_RX.match(v):
        raise ApiError(400, "Please enter a valid date.")
    return v


def intlist(d, key):
    v = d.get(key) or []
    if not isinstance(v, list):
        raise ApiError(400, "Invalid selection.")
    try:
        return [int(x) for x in v]
    except (TypeError, ValueError):
        raise ApiError(400, "Invalid selection.")


def fk(d, key, table, required=False):
    v = d.get(key)
    if v in (None, "", 0, "0"):
        if required:
            raise ApiError(400, "Please choose a %s." % key.replace("_id", "").replace("_", " "))
        return None
    if not db.one("SELECT id FROM %s WHERE id=?" % table, (v,)):
        raise ApiError(400, "Invalid selection for %s." % key.replace("_id", ""))
    return int(v)


def crud(path, table, spec, order="id", decorate=None, post_save=None, on_delete=None, auth="admin"):
    def get(rid):
        r = db.one("SELECT * FROM %s WHERE id=?" % table, (rid,))
        return decorate([r])[0] if decorate else r

    @route("GET", "/api/admin/" + path, auth)
    def listing(req):
        rows = db.all("SELECT * FROM %s ORDER BY %s" % (table, order))
        return decorate(rows) if decorate else rows

    @route("POST", "/api/admin/" + path, auth)
    def create(req):
        d = req.json()
        vals = {k: f(d) for k, f in spec.items()}
        rid = db.run("INSERT INTO %s(%s) VALUES(%s)" % (table, ",".join(vals), ",".join("?" * len(vals))), tuple(vals.values()))
        if post_save:
            post_save(rid, d, True)
        return get(rid)

    @route("PUT", "/api/admin/%s/<int:id>" % path, auth)
    def update(req):
        rid = req.params["id"]
        if not db.one("SELECT id FROM %s WHERE id=?" % table, (rid,)):
            raise ApiError(404, "Not found.")
        d = req.json()
        vals = {k: f(d) for k, f in spec.items()}
        db.run("UPDATE %s SET %s WHERE id=?" % (table, ",".join(k + "=?" for k in vals)), (*vals.values(), rid))
        if post_save:
            post_save(rid, d, False)
        return get(rid)

    @route("DELETE", "/api/admin/%s/<int:id>" % path, auth)
    def delete(req):
        rid = req.params["id"]
        if on_delete:
            on_delete(rid)
        try:
            db.run("DELETE FROM %s WHERE id=?" % table, (rid,))
        except sqlite3.IntegrityError:
            raise ApiError(409, "This item is still in use, so it cannot be deleted. You can disable it instead.")
        return {"ok": True}


# ---------- uploads ----------
@route("POST", "/api/admin/upload", "admin")
def upload(req):
    _, files = req.multipart()
    if not files:
        raise ApiError(400, "Please choose an image to upload.")
    return {"filenames": [uploads.save_image(f[2]) for f in files[:20]]}


# ---------- service categories / services ----------
crud("categories", "categories", {
    "name": lambda d: text(d, "name", 80, True, "Category name"), "description": lambda d: text(d, "description", 300),
    "sort": lambda d: int(number(d, "sort", minv=0) or 0), "active": lambda d: flag(d, "active", 1)}, "sort,id")


def services_decorate(rows):
    for r in rows:
        r["staff_ids"] = [x["staff_id"] for x in db.all("SELECT staff_id FROM staff_services WHERE service_id=?", (r["id"],))]
        r["avail_days"] = json.loads(r["avail_days"] or "[0,1,2,3,4,5,6]")
        r["category_name"] = db.scalar("SELECT name FROM categories WHERE id=?", (r["category_id"],))
    return rows


def days(d):
    v = intlist(d, "avail_days") if d.get("avail_days") is not None else list(range(7))
    if any(x < 0 or x > 6 for x in v):
        raise ApiError(400, "Invalid days.")
    return json.dumps(sorted(set(v)))


def services_save(rid, d, created):
    db.run("DELETE FROM staff_services WHERE service_id=?", (rid,))
    for sid in set(intlist(d, "staff_ids")):
        if db.one("SELECT id FROM staff WHERE id=?", (sid,)):
            db.run("INSERT INTO staff_services VALUES(?,?)", (sid, rid))


crud("services", "services", {
    "category_id": lambda d: fk(d, "category_id", "categories", True), "name": lambda d: text(d, "name", 120, True, "Service name"),
    "description": lambda d: text(d, "description", 1500), "price": lambda d: number(d, "price", minv=0, maxv=1000000),
    "duration_min": lambda d: int(number(d, "duration_min", True, 5, 720, "Duration") or 60), "image": img,
    "active": lambda d: flag(d, "active", 1), "avail_days": days, "sort": lambda d: int(number(d, "sort", minv=0) or 0)},
    "category_id,sort,id", services_decorate, services_save)


# ---------- staff ----------
def staff_decorate(rows):
    for r in rows:
        r["service_ids"] = [x["service_id"] for x in db.all("SELECT service_id FROM staff_services WHERE staff_id=?", (r["id"],))]
        h = {x["weekday"]: x for x in db.all("SELECT * FROM staff_hours WHERE staff_id=?", (r["id"],))}
        r["hours"] = [{"weekday": i, "custom": i in h, "off": bool(h[i]["off"]) if i in h else False, "start": h[i]["start"] if i in h else "", "end": h[i]["end"] if i in h else ""} for i in range(7)]
        u = db.one("SELECT id,email,can_chat,active FROM users WHERE staff_id=? AND role='staff'", (r["id"],))
        r["login"] = u
    return rows


def staff_save(rid, d, created):
    db.run("DELETE FROM staff_services WHERE staff_id=?", (rid,))
    for sid in set(intlist(d, "service_ids")):
        if db.one("SELECT id FROM services WHERE id=?", (sid,)):
            db.run("INSERT INTO staff_services VALUES(?,?)", (rid, sid))
    if isinstance(d.get("hours"), list):
        db.run("DELETE FROM staff_hours WHERE staff_id=?", (rid,))
        for h in d["hours"]:
            if not h.get("custom"):
                continue
            wd = int(h.get("weekday"))
            off = flag(h, "off")
            if not off and not (TIME_RX.match(h.get("start") or "") and TIME_RX.match(h.get("end") or "") and h["start"] < h["end"]):
                raise ApiError(400, "Please enter valid working hours (start before end).")
            db.run('INSERT INTO staff_hours(staff_id,weekday,start,"end",off) VALUES(?,?,?,?,?)', (rid, wd, h.get("start") or None, h.get("end") or None, off))


def staff_delete(rid):
    db.run("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE staff_id=?)", (rid,))
    db.run("DELETE FROM users WHERE staff_id=?", (rid,))


crud("staff", "staff", {"name": lambda d: text(d, "name", 80, True, "Name"), "specialty": lambda d: text(d, "specialty", 160), "bio": lambda d: text(d, "bio", 800),
                         "image": img, "active": lambda d: flag(d, "active", 1), "sort": lambda d: int(number(d, "sort", minv=0) or 0)},
     "sort,id", staff_decorate, staff_save, staff_delete)


@route("POST", "/api/admin/staff/<int:id>/login", "admin")
def staff_login(req):
    sid, d = req.params["id"], req.json()
    if not db.one("SELECT id FROM staff WHERE id=?", (sid,)):
        raise ApiError(404, "Staff member not found.")
    mail = text(d, "email", 120, True, "Email").lower()
    if not EMAIL_RX.match(mail):
        raise ApiError(400, "Please enter a valid email address.")
    pw = str(d.get("password") or "")
    u = db.one("SELECT * FROM users WHERE staff_id=? AND role='staff'", (sid,))
    if db.one("SELECT id FROM users WHERE email=? AND id!=?", (mail, u["id"] if u else 0)):
        raise ApiError(409, "That email is already used by another account.")
    if pw and len(pw) < 8:
        raise ApiError(400, "Password must be at least 8 characters.")
    name = db.scalar("SELECT name FROM staff WHERE id=?", (sid,))
    if u:
        db.run("UPDATE users SET email=?,can_chat=?,active=? WHERE id=?", (mail, flag(d, "can_chat"), flag(d, "active", 1), u["id"]))
        if pw:
            db.run("UPDATE users SET password_hash=? WHERE id=?", (security.hash_password(pw), u["id"]))
            db.run("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    else:
        if not pw:
            raise ApiError(400, "Please set a password (at least 8 characters).")
        db.run("INSERT INTO users(role,name,email,password_hash,can_chat,staff_id,created) VALUES('staff',?,?,?,?,?,?)", (name, mail, security.hash_password(pw), flag(d, "can_chat"), sid, db.now_str()))
    return {"ok": True}


@route("DELETE", "/api/admin/staff/<int:id>/login", "admin")
def staff_login_delete(req):
    staff_delete(req.params["id"])
    return {"ok": True}


# ---------- products ----------
crud("product-categories", "product_categories", {"name": lambda d: text(d, "name", 80, True, "Category name"), "sort": lambda d: int(number(d, "sort", minv=0) or 0)}, "sort,id",
     on_delete=lambda rid: db.run("UPDATE products SET category_id=NULL WHERE category_id=?", (rid,)))


def products_decorate(rows):
    for r in rows:
        r["images"] = db.all("SELECT id,filename,caption FROM product_images WHERE product_id=? ORDER BY sort,id", (r["id"],))
        r["category_name"] = db.scalar("SELECT name FROM product_categories WHERE id=?", (r["category_id"],)) if r["category_id"] else ""
    return rows


def product_delete(rid):
    for i in db.all("SELECT filename FROM product_images WHERE product_id=?", (rid,)):
        uploads.delete_image(i["filename"])


crud("products", "products", {
    "category_id": lambda d: fk(d, "category_id", "product_categories"), "name": lambda d: text(d, "name", 140, True, "Product name"),
    "description": lambda d: text(d, "description", 2000), "price": lambda d: number(d, "price", True, 0, 1000000, "Price"),
    "stock": lambda d: int(number(d, "stock", minv=0) or 0), "active": lambda d: flag(d, "active", 1)},
    "id DESC", products_decorate, lambda rid, d, c: c and db.run("UPDATE products SET created=? WHERE id=?", (db.now_str(), rid)), product_delete)


@route("POST", "/api/admin/products/<int:id>/images", "admin")
def product_images_add(req):
    pid = req.params["id"]
    if not db.one("SELECT id FROM products WHERE id=?", (pid,)):
        raise ApiError(404, "Product not found.")
    _, files = req.multipart()
    if not files:
        raise ApiError(400, "Please choose one or more images.")
    nxt = (db.scalar("SELECT MAX(sort) FROM product_images WHERE product_id=?", (pid,)) or 0) + 1
    for k, (_, _, data) in enumerate(files):
        db.run("INSERT INTO product_images(product_id,filename,sort) VALUES(?,?,?)", (pid, uploads.save_image(data), nxt + k))
    return products_decorate([db.one("SELECT * FROM products WHERE id=?", (pid,))])[0]


@route("DELETE", "/api/admin/product-images/<int:id>", "admin")
def product_image_delete(req):
    r = db.one("SELECT * FROM product_images WHERE id=?", (req.params["id"],))
    if not r:
        raise ApiError(404, "Image not found.")
    db.run("DELETE FROM product_images WHERE id=?", (r["id"],))
    uploads.delete_image(r["filename"])
    return {"ok": True}


@route("PUT", "/api/admin/products/<int:id>/images/order", "admin")
def product_images_order(req):
    for k, i in enumerate(intlist(req.json(), "ids")):
        db.run("UPDATE product_images SET sort=? WHERE id=? AND product_id=?", (k, i, req.params["id"]))
    return {"ok": True}


# ---------- promotions ----------
def promo_decorate(rows):
    for r in rows:
        r["service_ids"] = json.loads(r["service_ids"] or "[]")
    return rows


def promo_discount_type(d):
    v = d.get("discount_type")
    if v not in ("percent", "fixed"):
        raise ApiError(400, "Please choose a discount type.")
    return v


def promo_value(d):
    v = number(d, "discount_value", True, 0, 1000000, "Discount")
    if d.get("discount_type") == "percent" and v > 100:
        raise ApiError(400, "A percentage discount cannot be more than 100.")
    return v


def promo_dates(d):
    a, b = datev(d, "start_date"), datev(d, "end_date")
    if a and b and a > b:
        raise ApiError(400, "The end date must be after the start date.")
    return a


def promo_save(rid, d, created):
    if created:
        db.run("UPDATE promotions SET created=? WHERE id=?", (db.now_str(), rid))
        if flag(d, "active", 1):
            title = text(d, "title", 120)
            for u in db.all("SELECT id FROM users WHERE role='customer' AND active=1"):
                notify.notify(u["id"], "promotion", "New promotion: " + title, text(d, "description", 160), "#/promotions")


crud("promotions", "promotions", {
    "title": lambda d: text(d, "title", 120, True, "Title"), "description": lambda d: text(d, "description", 1500), "image": img,
    "discount_type": promo_discount_type, "discount_value": promo_value, "service_ids": lambda d: json.dumps(intlist(d, "service_ids")),
    "requires_all": lambda d: flag(d, "requires_all"), "start_date": promo_dates, "end_date": lambda d: datev(d, "end_date"), "active": lambda d: flag(d, "active", 1)},
    "id DESC", promo_decorate, promo_save)

# ---------- closures / blocked time ----------
def block_time(key):
    def f(d):
        v = text(d, key, 5)
        if v and not TIME_RX.match(v):
            raise ApiError(400, "Please enter a valid time.")
        if bool(text(d, "start_time", 5)) != bool(text(d, "end_time", 5)):
            raise ApiError(400, "Enter both a start and an end time, or leave both empty to block the whole day.")
        if text(d, "start_time", 5) and text(d, "start_time", 5) >= text(d, "end_time", 5):
            raise ApiError(400, "The end time must be after the start time.")
        return v
    return f


def block_to(d):
    a, b = datev(d, "date_from", True), datev(d, "date_to") or datev(d, "date_from")
    if b < a:
        raise ApiError(400, "The end date must be on or after the start date.")
    return b


crud("blocks", "blocks", {"staff_id": lambda d: fk(d, "staff_id", "staff"), "date_from": lambda d: datev(d, "date_from", True), "date_to": block_to,
                           "start_time": block_time("start_time"), "end_time": block_time("end_time"), "reason": lambda d: text(d, "reason", 160)},
     "date_from DESC", lambda rows: [dict(r, staff_name=db.scalar("SELECT name FROM staff WHERE id=?", (r["staff_id"],)) if r["staff_id"] else "Whole salon") for r in rows])

crud("ai-knowledge", "ai_knowledge", {"keywords": lambda d: text(d, "keywords", 300, True, "Keywords"), "answer": lambda d: text(d, "answer", 1000, True, "Answer"), "active": lambda d: flag(d, "active", 1)})


# ---------- appointments ----------
def staff_scope(req):
    return req.user["staff_id"] if req.user["role"] == "staff" else None


@route("GET", "/api/admin/appointments", "staff")
def appts(req):
    q = "SELECT DISTINCT a.* FROM appointments a LEFT JOIN appointment_items i ON i.appointment_id=a.id WHERE 1=1"
    a = []
    own = staff_scope(req)
    if req.user["role"] == "staff":
        q += " AND i.staff_id=?"; a.append(own or -1)
    for k, sql in (("date_from", " AND a.date>=?"), ("date_to", " AND a.date<=?"), ("status", " AND a.status=?"), ("service_id", " AND i.service_id=?")):
        if req.query.get(k):
            q += sql; a.append(req.query[k])
    if req.query.get("staff_id") and req.user["role"] == "admin":
        q += " AND i.staff_id=?"; a.append(req.query["staff_id"])
    if req.query.get("q"):
        q += " AND (a.customer_name LIKE ? OR a.customer_phone LIKE ? OR a.ref LIKE ?)"; a += ["%" + req.query["q"][:40] + "%"] * 3
    rows = db.all(q + " ORDER BY a.date DESC, a.start_time DESC LIMIT 600", a)
    for r in rows:
        booking.appt_detail(r)
        if req.user["role"] == "staff":
            r["customer_email"] = ""
            r["payment"] = None
    return rows


def get_appt(req, id_key="id"):
    a = db.one("SELECT * FROM appointments WHERE id=?", (req.params[id_key],))
    if not a:
        raise ApiError(404, "Appointment not found.")
    if req.user["role"] == "staff" and not db.one("SELECT id FROM appointment_items WHERE appointment_id=? AND staff_id=?", (a["id"], req.user["staff_id"] or -1)):
        raise ApiError(403, "You can only view your own appointments.")
    return a


@route("PUT", "/api/admin/appointments/<int:id>", "staff")
def appt_update(req):
    a, d = get_appt(req), req.json()
    if "admin_notes" in d:
        db.run("UPDATE appointments SET admin_notes=?,updated=? WHERE id=?", (text(d, "admin_notes", 1000), db.now_str(), a["id"]))
    st = d.get("status")
    if st and st != a["status"]:
        if req.user["role"] == "staff" and st != "in_progress":
            raise ApiError(403, "Staff can mark appointments as In Progress. Ask the owner for other changes.")
        if st not in ("pending", "confirmed", "in_progress", "cancelled", "no_show"):
            raise ApiError(400, "Use “Complete & record payment” to complete an appointment.")
        if a["status"] in ("completed", "cancelled", "no_show"):
            raise ApiError(400, "This appointment is already %s and can no longer change status." % a["status"].replace("_", " "))
        if st == "cancelled":
            booking.cancel(a, True, text(d, "reason", 200))
        else:
            db.run("UPDATE appointments SET status=?,updated=? WHERE id=?", (st, db.now_str(), a["id"]))
            if st == "confirmed":
                notify.notify_appointment(a, "booking", "Booking confirmed", "Your booking %s on %s is confirmed. We look forward to seeing you!" % (a["ref"], booking.pretty(a["date"], a["start_time"])))
    return booking.appt_detail(db.one("SELECT * FROM appointments WHERE id=?", (a["id"],)))


@route("POST", "/api/admin/appointments", "admin")
def appt_create(req):
    return {"appointment": booking.create_booking(req.json(), None, admin=True)}


@route("POST", "/api/admin/appointments/<int:id>/reschedule", "admin")
def appt_resched(req):
    d = req.json()
    return {"appointment": booking.reschedule(get_appt(req), d.get("date"), d.get("time"), admin=True)}


@route("POST", "/api/admin/appointments/<int:id>/complete", "admin")
def appt_complete(req):
    a, d = get_appt(req), req.json()
    if a["status"] in ("completed", "cancelled", "no_show"):
        raise ApiError(400, "This appointment is already %s." % a["status"].replace("_", " "))
    items = db.all("SELECT * FROM appointment_items WHERE appointment_id=?", (a["id"],))
    given = {int(x["id"]): x.get("price") for x in d.get("items", []) if isinstance(x, dict) and str(x.get("id", "")).isdigit()}
    rows = []
    for i in items:
        p = number({"p": given[i["id"]]}, "p", True, 0, 1000000, "Price for %s" % i["service_name"]) if i["id"] in given else i["price"]
        if p is None:
            raise ApiError(400, "Please enter the price charged for %s." % i["service_name"])
        rows.append({"id": i["id"], "service_id": i["service_id"], "price": round(p, 2)})
    promo_id = d["promo_id"] if "promo_id" in d else a["promo_id"]
    promo = db.one("SELECT * FROM promotions WHERE id=?", (promo_id,)) if promo_id else None
    if promo_id and not promo:
        raise ApiError(400, "Promotion not found.")
    gross = round(sum(r["price"] for r in rows), 2)
    disc = booking.promo_discount(promo, rows)
    net = round(gross - disc, 2)
    paid = flag(d, "paid", 1)
    method = text(d, "method", 40)
    if paid and method not in db.setting("payment_methods_record", []):
        raise ApiError(400, "Please choose how the customer paid.")
    with db.tx():
        for r in rows:
            db.run("UPDATE appointment_items SET price=? WHERE id=?", (r["price"], r["id"]))
        db.run("UPDATE appointments SET status='completed',promo_id=?,updated=? WHERE id=?", (promo["id"] if promo else None, db.now_str(), a["id"]))
        db.run("INSERT INTO payments(appointment_id,gross,discount,net,method,status,paid_at,recorded_by,created) VALUES(?,?,?,?,?,?,?,?,?)",
               (a["id"], gross, disc, net, method if paid else "", "paid" if paid else "pending", db.now_str() if paid else None, req.user["id"], db.now_str()))
    notify.notify(a["user_id"], "review_request", "How was your visit?", "Thank you for visiting! We would love your feedback.", "#/reviews?write=1")
    return booking.appt_detail(db.one("SELECT * FROM appointments WHERE id=?", (a["id"],)))


def get_payment(req):
    p = db.one("SELECT * FROM payments WHERE id=?", (req.params["id"],))
    if not p:
        raise ApiError(404, "Payment not found.")
    return p


@route("POST", "/api/admin/payments/<int:id>/pay", "admin")
def pay(req):
    p, d = get_payment(req), req.json()
    if p["status"] != "pending":
        raise ApiError(400, "Only pending payments can be marked as paid.")
    method = text(d, "method", 40)
    if method not in db.setting("payment_methods_record", []):
        raise ApiError(400, "Please choose how the customer paid.")
    db.run("UPDATE payments SET status='paid',method=?,paid_at=?,recorded_by=? WHERE id=?", (method, db.now_str(), req.user["id"], p["id"]))
    return {"ok": True}


@route("POST", "/api/admin/payments/<int:id>/refund", "admin")
def refund(req):
    p, d = get_payment(req), req.json()
    if p["status"] != "paid":
        raise ApiError(400, "Only paid transactions can be refunded.")
    remaining = round(p["net"] - p["refunded_amount"], 2)
    amt = number(d, "amount", minv=0.01, label="Refund amount") or remaining
    if amt > remaining + 0.001:
        raise ApiError(400, "The refund cannot be more than the amount still held (%.2f)." % remaining)
    reason = text(d, "reason", 200, True, "Refund reason")
    full = amt >= remaining - 0.001
    db.run("UPDATE payments SET refunded_amount=?,status=?,reason=? WHERE id=?", (round(p["refunded_amount"] + amt, 2), "refunded" if full else "paid", reason, p["id"]))
    return {"ok": True, "full": full}


@route("POST", "/api/admin/payments/<int:id>/void", "admin")
def void(req):
    p, d = get_payment(req), req.json()
    if p["status"] not in ("pending", "paid"):
        raise ApiError(400, "This transaction has already been refunded or voided.")
    db.run("UPDATE payments SET status='voided',reason=? WHERE id=?", (text(d, "reason", 200, True, "Void reason"), p["id"]))
    return {"ok": True}


# ---------- revenue ----------
def rev_filters(req):
    q = req.query
    gi = lambda k: int(q[k]) if q.get(k, "").isdigit() else None
    return dict(preset=q.get("preset") or None, d_from=q.get("from"), d_to=q.get("to"), category_id=gi("category_id"), staff_id=gi("staff_id"), service_id=gi("service_id"), method=q.get("method") or None)


@route("GET", "/api/admin/revenue", "admin")
def revenue_view(req):
    return {"cards": revenue.summary_cards(), "filtered": revenue.collect(**rev_filters(req)), "methods": db.setting("payment_methods_record", [])}


@route("GET", "/api/admin/revenue/report", "admin")
def revenue_report(req):
    data = revenue.collect(**rev_filters(req))
    if req.query.get("format") == "csv":
        return {"_raw": revenue.to_csv(data).encode("utf-8"), "_ctype": "text/csv; charset=utf-8", "_filename": "revenue-report-%s.csv" % db.now_str()[:10]}
    return data


# ---------- dashboard & analytics ----------
@route("GET", "/api/admin/dashboard", "admin")
def dashboard(req):
    today = booking.now_local().date()
    ts = today.isoformat()
    todays = db.all("SELECT * FROM appointments WHERE date=? AND status!='cancelled' ORDER BY start_time", (ts,))
    for a in todays:
        booking.appt_detail(a)
    upcoming = db.all("SELECT * FROM appointments WHERE date>? AND status IN ('pending','confirmed') ORDER BY date,start_time LIMIT 8", (ts,))
    for a in upcoming:
        booking.appt_detail(a)
    c = lambda sql, a=(): db.scalar(sql, a) or 0
    start = today - dt.timedelta(days=13)
    per = {r["date"]: r["n"] for r in db.all("SELECT date,COUNT(*) n FROM appointments WHERE date BETWEEN ? AND ? AND status!='cancelled' GROUP BY date", (start.isoformat(), ts))}
    by_day = [{"label": (start + dt.timedelta(days=i)).strftime("%d %b"), "value": per.get((start + dt.timedelta(days=i)).isoformat(), 0)} for i in range(14)]
    wk_start = today - dt.timedelta(days=today.weekday() + 77)
    wk = [0] * 12
    for r in db.all("SELECT date FROM appointments WHERE date>=? AND status!='cancelled'", (wk_start.isoformat(),)):
        idx = (dt.date.fromisoformat(r["date"]) - wk_start).days // 7
        if 0 <= idx < 12:
            wk[idx] += 1
    trend = [{"label": (wk_start + dt.timedelta(days=7 * i)).strftime("%d %b"), "value": wk[i]} for i in range(12)]
    rating = rating_summary()
    return {
        "today": todays, "upcoming": upcoming,
        "counts": {"customers": c("SELECT COUNT(*) FROM users WHERE role='customer'"), "services": c("SELECT COUNT(*) FROM services WHERE active=1"),
                   "products": c("SELECT COUNT(*) FROM products WHERE active=1"), "staff": c("SELECT COUNT(*) FROM staff WHERE active=1"),
                   "reviews": rating["total"], "pending": c("SELECT COUNT(*) FROM appointments WHERE status='pending'"),
                   "completed": c("SELECT COUNT(*) FROM appointments WHERE status='completed'"), "unanswered": c("SELECT COUNT(*) FROM conversations WHERE admin_unread>0 AND archived=0")},
        "rating": rating, "has_payments": c("SELECT COUNT(*) FROM payments") > 0,
        "revenue": {"today": revenue.collect("today")["totals"], "month": revenue.collect("month")["totals"], "all": revenue.collect(None)["totals"]},
        "charts": {
            "by_day": by_day, "trend": trend,
            "popular": [{"label": r["service_name"], "value": r["n"]} for r in db.all("SELECT i.service_name, COUNT(*) n FROM appointment_items i JOIN appointments a ON a.id=i.appointment_id WHERE a.status!='cancelled' GROUP BY i.service_name ORDER BY n DESC LIMIT 8")],
            "staff": [{"label": r["name"], "value": r["n"]} for r in db.all("SELECT st.name, COUNT(*) n FROM appointment_items i JOIN appointments a ON a.id=i.appointment_id JOIN staff st ON st.id=i.staff_id WHERE a.status!='cancelled' GROUP BY st.id ORDER BY n DESC")],
            "ratings": [{"label": "%d★" % k, "value": v} for k, v in sorted(rating["distribution"].items(), reverse=True)]},
        "alerts": {"unassigned_services": [r["name"] for r in db.all("SELECT name FROM services s WHERE active=1 AND NOT EXISTS(SELECT 1 FROM staff_services ss JOIN staff st ON st.id=ss.staff_id AND st.active=1 WHERE ss.service_id=s.id)")],
                   "unpriced_services": c("SELECT COUNT(*) FROM services WHERE active=1 AND price IS NULL"),
                   "pending_payments": c("SELECT COUNT(*) FROM payments WHERE status='pending'")}}


@route("GET", "/api/admin/analytics", "admin")
def analytics(req):
    rows = db.all("SELECT date,start_time,status FROM appointments")
    valid = [r for r in rows if r["status"] != "cancelled"]
    heat = [[0] * 24 for _ in range(7)]
    for r in valid:
        heat[dt.date.fromisoformat(r["date"]).weekday()][int(r["start_time"][:2])] += 1
    total = len(valid)
    parts = {"Morning (before 12)": (0, 12), "Afternoon (12-5)": (12, 17), "Evening (5-10)": (17, 24)}
    buckets = []
    hrs = db.setting("hours")
    for d in range(7):
        if hrs[d].get("closed"):
            continue
        for name, (lo, hi) in parts.items():
            buckets.append({"day": hrs[d]["day"], "part": name, "count": sum(heat[d][lo:hi])})
    buckets.sort(key=lambda b: -b["count"])
    n = len(rows)
    return {"total": total, "heat": heat, "peak": buckets[:3] if total else [], "off_peak": list(reversed(buckets[-3:])) if total else [],
            "cancel_rate": round(100 * sum(1 for r in rows if r["status"] == "cancelled") / n, 1) if n else 0,
            "no_show_rate": round(100 * sum(1 for r in rows if r["status"] == "no_show") / n, 1) if n else 0,
            "hours": [{"day": h["day"], "open": h["open"], "close": h["close"], "closed": h.get("closed")} for h in hrs]}


# ---------- customers ----------
@route("GET", "/api/admin/customers", "admin")
def customers(req):
    q = "SELECT * FROM users WHERE role='customer'"
    a = []
    if req.query.get("q"):
        q += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ?)"; a += ["%" + req.query["q"][:40] + "%"] * 3
    out = []
    for u in db.all(q + " ORDER BY created DESC LIMIT 500", a):
        s = db.one("SELECT COUNT(*) n, SUM(status='completed') done, MAX(date) last FROM appointments WHERE user_id=?", (u["id"],))
        spent = db.scalar("SELECT SUM(p.net-p.refunded_amount) FROM payments p JOIN appointments a ON a.id=p.appointment_id WHERE a.user_id=? AND p.status='paid' AND a.status='completed'", (u["id"],)) or 0
        out.append({"id": u["id"], "name": u["name"], "email": u["email"], "phone": u["phone"], "active": u["active"], "created": u["created"], "appointments": s["n"], "completed": s["done"] or 0, "last_visit": s["last"], "spent": round(spent, 2), "registered": True})
    if not req.query.get("q") or True:
        for g in db.all("SELECT customer_name name, customer_phone phone, COUNT(*) n, SUM(status='completed') done, MAX(date) last FROM appointments WHERE user_id IS NULL "
                        + ("AND (customer_name LIKE ? OR customer_phone LIKE ?) " if req.query.get("q") else "") + "GROUP BY customer_phone ORDER BY last DESC LIMIT 200",
                        ["%" + req.query["q"][:40] + "%"] * 2 if req.query.get("q") else []):
            out.append({"id": None, "name": g["name"], "email": "", "phone": g["phone"], "active": 1, "created": "", "appointments": g["n"], "completed": g["done"] or 0, "last_visit": g["last"], "spent": 0, "registered": False})
    return out


@route("GET", "/api/admin/customers/<int:id>", "admin")
def customer_detail(req):
    u = db.one("SELECT id,name,email,phone,active,created FROM users WHERE id=? AND role='customer'", (req.params["id"],))
    if not u:
        raise ApiError(404, "Customer not found.")
    appts_ = db.all("SELECT * FROM appointments WHERE user_id=? ORDER BY date DESC", (u["id"],))
    for a in appts_:
        booking.appt_detail(a)
    return {"customer": u, "appointments": appts_, "reviews": db.all("SELECT * FROM reviews WHERE user_id=? ORDER BY created DESC", (u["id"],))}


@route("PUT", "/api/admin/customers/<int:id>", "admin")
def customer_update(req):
    db.run("UPDATE users SET active=? WHERE id=? AND role='customer'", (flag(req.json(), "active", 1), req.params["id"]))
    if not flag(req.json(), "active", 1):
        db.run("DELETE FROM sessions WHERE user_id=?", (req.params["id"],))
    return {"ok": True}


# ---------- reviews & testimonials ----------
@route("GET", "/api/admin/reviews", "admin")
def admin_reviews(req):
    w, a = ["1=1"], []
    for k, col in (("rating", "r.rating"), ("service_id", "r.service_id"), ("staff_id", "r.staff_id"), ("featured", "r.featured"), ("visible", "r.visible")):
        if req.query.get(k) not in (None, ""):
            w.append("%s=?" % col); a.append(req.query[k])
    return db.all("SELECT r.*, sv.name AS service_name, st.name AS staff_name FROM reviews r LEFT JOIN services sv ON sv.id=r.service_id LEFT JOIN staff st ON st.id=r.staff_id WHERE %s ORDER BY r.created DESC LIMIT 400" % " AND ".join(w), a)


@route("PUT", "/api/admin/reviews/<int:id>", "admin")
def review_update(req):
    r = db.one("SELECT * FROM reviews WHERE id=?", (req.params["id"],))
    if not r:
        raise ApiError(404, "Review not found.")
    d = req.json()
    vis, feat = flag(d, "visible", r["visible"]), flag(d, "featured", r["featured"])
    db.run("UPDATE reviews SET visible=?,featured=? WHERE id=?", (vis, feat, r["id"]))
    if feat and not r["featured"] and r["user_id"]:
        notify.notify(r["user_id"], "review", "Your review is featured", "Thank you! Your review is now featured on our home page.", "#/reviews")
    return {"ok": True}


@route("DELETE", "/api/admin/reviews/<int:id>", "admin")
def review_delete(req):
    r = db.one("SELECT image FROM reviews WHERE id=?", (req.params["id"],))
    if r:
        uploads.delete_image(r["image"])
    db.run("DELETE FROM reviews WHERE id=?", (req.params["id"],))
    return {"ok": True}


@route("POST", "/api/admin/testimonials", "admin")
def testimonial_create(req):
    d = req.json()
    rating = int(number(d, "rating", True, 1, 5, "Rating"))
    rid = db.run("INSERT INTO reviews(author_name,rating,body,image,featured,source,created) VALUES(?,?,?,?,?,'admin',?)",
                 (text(d, "author_name", 80, True, "Customer name"), rating, text(d, "body", 1000, True, "Testimonial"), img(d), flag(d, "featured", 1), db.now_str()))
    return {"id": rid}


# ---------- chat inbox ----------
def chat_guard(req):
    if req.user["role"] == "staff" and not req.user["can_chat"]:
        raise ApiError(403, "You do not have access to customer messages.")


@route("GET", "/api/admin/conversations", "staff")
def conversations(req):
    chat_guard(req)
    q = ("SELECT c.*, u.name, u.email, u.phone, (SELECT body FROM messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) AS last_body "
         "FROM conversations c JOIN users u ON u.id=c.user_id WHERE c.archived=? AND EXISTS(SELECT 1 FROM messages m WHERE m.conversation_id=c.id)")
    a = [1 if req.query.get("archived") == "1" else 0]
    if req.query.get("q"):
        q += " AND (u.name LIKE ? OR u.email LIKE ? OR u.phone LIKE ?)"; a += ["%" + req.query["q"][:40] + "%"] * 3
    return db.all(q + " ORDER BY c.last_message_at DESC LIMIT 200", a)


def conv(req):
    c = db.one("SELECT c.*, u.name, u.email, u.phone FROM conversations c JOIN users u ON u.id=c.user_id WHERE c.id=?", (req.params["id"],))
    if not c:
        raise ApiError(404, "Conversation not found.")
    return c


@route("GET", "/api/admin/conversations/<int:id>", "staff")
def conversation_view(req):
    chat_guard(req)
    c = conv(req)
    after = int(req.query.get("after", 0) or 0)
    msgs = db.all("SELECT id,sender,body,created FROM messages WHERE conversation_id=? AND id>? ORDER BY id", (c["id"], after))
    db.run("UPDATE conversations SET admin_unread=0 WHERE id=?", (c["id"],))
    return {"conversation": c, "messages": msgs}


@route("POST", "/api/admin/conversations/<int:id>/reply", "staff")
def conversation_reply(req):
    chat_guard(req)
    c = conv(req)
    body = text(req.json(), "body", 1000, True, "Message")
    mid = db.run("INSERT INTO messages(conversation_id,sender,sender_user_id,body,created) VALUES(?,?,?,?,?)", (c["id"], "salon", req.user["id"], body, db.now_str()))
    db.run("UPDATE conversations SET customer_unread=customer_unread+1, admin_unread=0, archived=0, last_message_at=? WHERE id=?", (db.now_str(), c["id"]))
    notify.notify(c["user_id"], "message", "%s replied" % db.setting("business_name"), body[:120], "#/chat/salon")
    return {"id": mid}


@route("POST", "/api/admin/conversations/<int:id>/archive", "staff")
def conversation_archive(req):
    chat_guard(req)
    db.run("UPDATE conversations SET archived=? WHERE id=?", (flag(req.json(), "archived", 1), conv(req)["id"]))
    return {"ok": True}


@route("POST", "/api/admin/conversations/<int:id>/read", "staff")
def conversation_read(req):
    chat_guard(req)
    db.run("UPDATE conversations SET admin_unread=0 WHERE id=?", (conv(req)["id"],))
    return {"ok": True}


# ---------- settings ----------
def s_str(n, req=False):
    return lambda v: text({"v": v}, "v", n, req)


def s_list(v, n=60, maxn=30):
    if not isinstance(v, list):
        raise ApiError(400, "Invalid list.")
    out = [str(x).strip() for x in v if str(x).strip()]
    if len(out) > maxn or any(len(x) > n for x in out):
        raise ApiError(400, "A list item is too long or there are too many items.")
    return out


def s_img(v):
    v = "" if v is None else str(v)
    if v and not IMG_RX.match(v):
        raise ApiError(400, "Invalid image reference.")
    return v


def s_hours(v):
    if not isinstance(v, list) or len(v) != 7:
        raise ApiError(400, "Please provide hours for all 7 days.")
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = []
    for i, h in enumerate(v):
        closed = bool(h.get("closed"))
        if not closed:
            if not (TIME_RX.match(h.get("open") or "") and TIME_RX.match(h.get("close") or "")) or h["open"] >= h["close"]:
                raise ApiError(400, "%s: opening time must be before closing time." % names[i])
        out.append({"day": names[i], "open": h.get("open") or "10:00", "close": h.get("close") or "22:00", "closed": closed})
    return out


def s_num(lo, hi, integer=True):
    def f(v):
        x = number({"v": v}, "v", True, lo, hi, "Value")
        return int(x) if integer else x
    return f


SETTING_RULES = {
    "business_name": s_str(100, True), "tagline": s_str(160), "description": s_str(1200), "business_type": s_str(120), "owner_name": s_str(80), "owner_title": s_str(80),
    "owner_bio": s_str(1200), "owner_image": s_img, "address": s_str(250, True), "area": s_str(120), "phone": s_str(30, True), "email": s_str(120), "website": s_str(160),
    "facebook_url": s_str(250), "hours": s_hours, "amenities": s_list, "payment_methods": s_list, "payment_methods_record": s_list, "hero_image": s_img,
    "gallery": lambda v: [s_img(x) for x in (v if isinstance(v, list) else [])][:30], "map_lat": s_num(-90, 90, False), "map_lng": s_num(-180, 180, False),
    "google_maps_key": s_str(120), "baseline_rating": s_num(0, 5, False), "baseline_count": s_num(0, 1000000), "default_duration": s_num(5, 720),
    "slot_step": s_num(5, 120), "min_notice_minutes": s_num(0, 10080), "booking_horizon_days": s_num(1, 730), "customer_change_cutoff_hours": s_num(0, 720, False),
    "auto_confirm": lambda v: bool(v), "appointment_policy": s_str(500)}


@route("GET", "/api/admin/settings", "admin")
def settings_get(req):
    s = dict(db.settings())
    s["_sms_ready"] = notify.sms_ready()
    s["_payment_gateway"] = __import__("app.config", fromlist=["x"]).PAYMENT_GATEWAY
    return s


@route("PUT", "/api/admin/settings", "admin")
def settings_put(req):
    d = req.json()
    clean = {}
    for k, v in d.items():
        if k not in SETTING_RULES:
            raise ApiError(400, "Unknown setting: %s" % k)
        clean[k] = SETTING_RULES[k](v)
    for k, v in clean.items():
        db.set_setting(k, v)
    return {"ok": True}
