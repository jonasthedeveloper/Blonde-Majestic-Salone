"""Public, authentication and customer endpoints."""
import json
from . import db, security, booking, notify, ai, uploads, config
from .web import route, ApiError, text, number, flag, EMAIL_RX, valid_phone, DATE_RX


def public_user(u):
    return {k: u[k] for k in ("id", "role", "name", "email", "phone", "staff_id", "can_chat")} if u else None


def rating_summary():
    """Average = (baseline_rating*baseline_count + sum of real ratings) / (baseline_count + real reviews).
    Set baseline_count to 0 in Settings to use real reviews only."""
    rows = db.all("SELECT rating, COUNT(*) n FROM reviews WHERE visible=1 GROUP BY rating")
    dist = {i: 0 for i in range(1, 6)}
    for r in rows:
        dist[r["rating"]] = r["n"]
    real_n = sum(dist.values())
    real_sum = sum(k * v for k, v in dist.items())
    bn = int(db.setting("baseline_count", 0) or 0)
    ba = float(db.setting("baseline_rating", 0) or 0)
    total = bn + real_n
    avg = (ba * bn + real_sum) / total if total else 0
    return {"average": round(avg, 2), "total": total, "real_total": real_n, "baseline_count": bn, "distribution": dist}


def review_rows(where="visible=1", args=(), limit=20, offset=0):
    return db.all("SELECT r.*, sv.name AS service_name, st.name AS staff_name FROM reviews r LEFT JOIN services sv ON sv.id=r.service_id "
                  "LEFT JOIN staff st ON st.id=r.staff_id WHERE %s ORDER BY r.created DESC LIMIT ? OFFSET ?" % where, (*args, limit, offset))


def with_staff(svcs):
    for s in svcs:
        s["staff"] = db.all("SELECT st.id,st.name FROM staff st JOIN staff_services ss ON ss.staff_id=st.id WHERE ss.service_id=? AND st.active=1 ORDER BY st.sort,st.id", (s["id"],))
        s["avail_days"] = json.loads(s["avail_days"] or "[0,1,2,3,4,5,6]")
    return svcs


@route("GET", "/api/public")
def bootstrap(req):
    cats = db.all("SELECT c.*, (SELECT COUNT(*) FROM services s WHERE s.category_id=c.id AND s.active=1) AS service_count FROM categories c WHERE c.active=1 ORDER BY c.sort,c.id")
    today = booking.now_local().date().isoformat()
    promos = db.all("SELECT * FROM promotions WHERE active=1 AND (start_date='' OR start_date<=?) AND (end_date='' OR end_date>=?) ORDER BY id DESC", (today, today))
    return {"settings": db.settings(), "categories": cats, "rating": rating_summary(),
            "testimonials": review_rows("visible=1 AND featured=1", (), 12), "promotions": promos,
            "staff": db.all("SELECT * FROM staff WHERE active=1 ORDER BY sort,id"),
            "sms_enabled": notify.sms_ready()}


@route("GET", "/api/services")
def services(req):
    q = "SELECT s.*, c.name AS category_name FROM services s JOIN categories c ON c.id=s.category_id WHERE s.active=1 AND c.active=1"
    a = []
    if req.query.get("category"):
        q += " AND s.category_id=?"; a.append(req.query["category"])
    if req.query.get("q"):
        q += " AND (s.name LIKE ? OR s.description LIKE ?)"; a += ["%" + req.query["q"][:60] + "%"] * 2
    if req.query.get("min"):
        q += " AND s.price>=?"; a.append(req.query["min"])
    if req.query.get("max"):
        q += " AND s.price<=?"; a.append(req.query["max"])
    return with_staff(db.all(q + " ORDER BY c.sort,c.id,s.sort,s.id", a))


@route("GET", "/api/services/<int:id>")
def service_detail(req):
    s = db.one("SELECT s.*, c.name AS category_name FROM services s JOIN categories c ON c.id=s.category_id WHERE s.id=? AND s.active=1 AND c.active=1", (req.params["id"],))
    if not s:
        raise ApiError(404, "Service not found.")
    s = with_staff([s])[0]
    s["related"] = with_staff(db.all("SELECT s.*, c.name AS category_name FROM services s JOIN categories c ON c.id=s.category_id WHERE s.category_id=? AND s.id!=? AND s.active=1 ORDER BY s.sort LIMIT 6", (s["category_id"], s["id"])))
    return s


@route("GET", "/api/staff")
def staff_list(req):
    st = db.all("SELECT * FROM staff WHERE active=1 ORDER BY sort,id")
    for s in st:
        s["services"] = db.all("SELECT sv.id,sv.name FROM services sv JOIN staff_services ss ON ss.service_id=sv.id WHERE ss.staff_id=? AND sv.active=1 ORDER BY sv.sort", (s["id"],))
        rr = db.one("SELECT AVG(rating) a, COUNT(*) n FROM reviews WHERE staff_id=? AND visible=1", (s["id"],))
        s["rating"] = round(rr["a"], 2) if rr["n"] else None
        s["review_count"] = rr["n"]
    return st


@route("GET", "/api/product-categories")
def pcats(req):
    return db.all("SELECT * FROM product_categories ORDER BY sort,id")


def with_images(ps):
    for p in ps:
        p["images"] = db.all("SELECT id,filename,caption FROM product_images WHERE product_id=? ORDER BY sort,id", (p["id"],))
    return ps


@route("GET", "/api/products")
def products(req):
    q = "SELECT p.*, c.name AS category_name FROM products p LEFT JOIN product_categories c ON c.id=p.category_id WHERE p.active=1"
    a = []
    if req.query.get("category"):
        q += " AND p.category_id=?"; a.append(req.query["category"])
    if req.query.get("q"):
        q += " AND (p.name LIKE ? OR p.description LIKE ?)"; a += ["%" + req.query["q"][:60] + "%"] * 2
    if req.query.get("min"):
        q += " AND p.price>=?"; a.append(req.query["min"])
    if req.query.get("max"):
        q += " AND p.price<=?"; a.append(req.query["max"])
    return with_images(db.all(q + " ORDER BY p.id DESC", a))


@route("GET", "/api/products/<int:id>")
def product(req):
    p = db.one("SELECT p.*, c.name AS category_name FROM products p LEFT JOIN product_categories c ON c.id=p.category_id WHERE p.id=? AND p.active=1", (req.params["id"],))
    if not p:
        raise ApiError(404, "Product not found.")
    return with_images([p])[0]


@route("GET", "/api/promotions")
def promotions(req):
    today = booking.now_local().date().isoformat()
    return db.all("SELECT * FROM promotions WHERE active=1 AND (end_date='' OR end_date>=?) ORDER BY id DESC", (today,))


@route("GET", "/api/reviews")
def reviews(req):
    w, a = ["visible=1"], []
    for k, col in (("rating", "r.rating"), ("service_id", "r.service_id"), ("staff_id", "r.staff_id")):
        if req.query.get(k):
            w.append("%s=?" % col); a.append(req.query[k])
    off = int(req.query.get("offset", 0) or 0)
    return {"summary": rating_summary(), "reviews": review_rows(" AND ".join(w), a, 12, off)}


@route("POST", "/api/reviews", "user")
def post_review(req):
    fields, files = req.multipart()
    try:
        rating = int(fields.get("rating", 0))
    except ValueError:
        rating = 0
    if not 1 <= rating <= 5:
        raise ApiError(400, "Please choose a rating from 1 to 5 stars.")
    body = text(fields, "body", 1000)
    if len(body) < 3:
        raise ApiError(400, "Please write a few words about your experience.")
    if security.rate_limited("review:%d" % req.user["id"], 5, 86400):
        raise ApiError(429, "You have reached today's review limit. Please try again tomorrow.")
    sid = int(fields["service_id"]) if (fields.get("service_id") or "").isdigit() else None
    stid = int(fields["staff_id"]) if (fields.get("staff_id") or "").isdigit() else None
    img = uploads.save_image(files[0][2]) if files else ""
    verified = 1 if db.scalar("SELECT COUNT(*) FROM appointments WHERE user_id=? AND status='completed'", (req.user["id"],)) else 0
    rid = db.run("INSERT INTO reviews(user_id,author_name,rating,body,image,service_id,staff_id,verified,created) VALUES(?,?,?,?,?,?,?,?,?)",
                 (req.user["id"], req.user["name"], rating, body, img, sid, stid, verified, db.now_str()))
    notify.notify_admins("review", "New %d-star review" % rating, "%s: %s" % (req.user["name"], body[:80]), "#/admin/reviews")
    return {"id": rid}


@route("POST", "/api/availability")
def availability(req):
    d = req.json()
    if not isinstance(d.get("items"), list):
        raise ApiError(400, "Please select at least one service.")
    ex = d.get("exclude_appointment_id")
    if ex:  # lets a person move an appointment into its own neighbouring time; customers only for their own booking
        ok = req.user and (req.user["role"] in ("admin", "staff") or db.one("SELECT id FROM appointments WHERE id=? AND user_id=?", (ex, req.user["id"])))
        ex = int(ex) if ok else None
    return booking.available_slots(booking.parse_date(d.get("date")), d["items"], exclude=ex, admin=bool(req.user and req.user["role"] in ("admin", "staff")))


@route("POST", "/api/book")
def book(req):
    d = req.json()
    if req.user and req.user["role"] == "customer":
        d.setdefault("customer_name", req.user["name"])
    if security.rate_limited("book:" + (req.ip or "x"), 20, 3600):
        raise ApiError(429, "Too many booking attempts. Please try again later.")
    a = booking.create_booking(d, req.user)
    return {"appointment": a}


@route("POST", "/api/ai-chat")
def ai_chat(req):
    msg = text(req.json(), "message", 500, True, "Message")
    if security.rate_limited("ai:" + (req.ip or "x"), 60, 600):
        raise ApiError(429, "Please slow down a little and try again shortly.")
    return ai.answer(msg)


# ---------------- auth ----------------
@route("POST", "/api/auth/register")
def register(req):
    d = req.json()
    name = text(d, "name", 80, True, "Name")
    mail = text(d, "email", 120, True, "Email").lower()
    phone = text(d, "phone", 25, True, "Phone number")
    pw = str(d.get("password") or "")
    if not EMAIL_RX.match(mail):
        raise ApiError(400, "Please enter a valid email address.")
    if not valid_phone(phone):
        raise ApiError(400, "Please enter a valid phone number.")
    if len(pw) < 8:
        raise ApiError(400, "Password must be at least 8 characters.")
    if security.rate_limited("reg:" + (req.ip or "x"), 10, 3600):
        raise ApiError(429, "Too many attempts. Please try again later.")
    if db.one("SELECT id FROM users WHERE email=?", (mail,)):
        raise ApiError(409, "An account with this email already exists. Try signing in.")
    uid = db.run("INSERT INTO users(role,name,email,phone,password_hash,created) VALUES('customer',?,?,?,?,?)", (name, mail, phone, security.hash_password(pw), db.now_str()))
    db.run("UPDATE appointments SET user_id=? WHERE user_id IS NULL AND (customer_phone=? OR (customer_email!='' AND customer_email=?))", (uid, phone, mail))
    notify.notify(uid, "welcome", "Welcome to %s" % db.setting("business_name"), "Your account is ready. You can now book and manage appointments.", "#/book")
    return login_response(db.one("SELECT * FROM users WHERE id=?", (uid,)))


def login_response(u):
    return {"user": public_user(u), "_set_cookie": security.create_session(u["id"])}


@route("POST", "/api/auth/login")
def login(req):
    d = req.json()
    mail = text(d, "email", 120).lower()
    if security.rate_limited("login:%s:%s" % (req.ip, mail), 8, 300):
        raise ApiError(429, "Too many sign-in attempts. Please wait a few minutes and try again.")
    u = db.one("SELECT * FROM users WHERE email=? AND active=1", (mail,))
    if not u or not security.verify_password(str(d.get("password") or ""), u["password_hash"]):
        raise ApiError(401, "Incorrect email or password.")
    return login_response(u)


@route("POST", "/api/auth/logout")
def logout(req):
    security.destroy_session(req.token)
    return {"ok": True, "_clear_cookie": True}


@route("GET", "/api/auth/me")
def me(req):
    return {"user": public_user(req.user)}


@route("PUT", "/api/auth/me", "user")
def update_me(req):
    d = req.json()
    name = text(d, "name", 80, True, "Name")
    phone = text(d, "phone", 25, True, "Phone number")
    if not valid_phone(phone):
        raise ApiError(400, "Please enter a valid phone number.")
    mail = text(d, "email", 120, True, "Email").lower()
    if not EMAIL_RX.match(mail):
        raise ApiError(400, "Please enter a valid email address.")
    if db.one("SELECT id FROM users WHERE email=? AND id!=?", (mail, req.user["id"])):
        raise ApiError(409, "That email is already used by another account.")
    db.run("UPDATE users SET name=?,phone=?,email=? WHERE id=?", (name, phone, mail, req.user["id"]))
    return {"user": public_user(db.one("SELECT * FROM users WHERE id=?", (req.user["id"],)))}


@route("POST", "/api/auth/password", "user")
def change_password(req):
    d = req.json()
    if not security.verify_password(str(d.get("current") or ""), req.user["password_hash"]):
        raise ApiError(400, "Your current password is incorrect.")
    new = str(d.get("new") or "")
    if len(new) < 8:
        raise ApiError(400, "New password must be at least 8 characters.")
    db.run("UPDATE users SET password_hash=? WHERE id=?", (security.hash_password(new), req.user["id"]))
    db.run("DELETE FROM sessions WHERE user_id=? AND token_hash!=?", (req.user["id"], security._th(req.token)))
    return {"ok": True}


# ---------------- customer area ----------------
@route("GET", "/api/my/appointments", "user")
def my_appointments(req):
    rows = db.all("SELECT * FROM appointments WHERE user_id=? ORDER BY date DESC, start_time DESC", (req.user["id"],))
    cutoff = float(db.setting("customer_change_cutoff_hours", 0) or 0)
    now = booking.now_local()
    import datetime as dt
    for a in rows:
        booking.appt_detail(a)
        start = dt.datetime.fromisoformat(a["date"] + "T" + a["start_time"])
        a["can_change"] = a["status"] in ("pending", "confirmed") and (not cutoff or (start - now).total_seconds() >= cutoff * 3600) and start > now
    return {"appointments": rows, "cutoff_hours": cutoff}


def own_appt(req):
    a = db.one("SELECT * FROM appointments WHERE id=? AND user_id=?", (req.params["id"], req.user["id"]))
    if not a:
        raise ApiError(404, "Appointment not found.")
    return a


@route("POST", "/api/my/appointments/<int:id>/cancel", "user")
def my_cancel(req):
    booking.cancel(own_appt(req))
    return {"ok": True}


@route("POST", "/api/my/appointments/<int:id>/reschedule", "user")
def my_resched(req):
    a = own_appt(req)
    d = req.json()
    cutoff = float(db.setting("customer_change_cutoff_hours", 0) or 0)
    import datetime as dt
    if cutoff and (dt.datetime.fromisoformat(a["date"] + "T" + a["start_time"]) - booking.now_local()).total_seconds() < cutoff * 3600:
        raise ApiError(400, "Appointments can only be changed at least %g hours before the start time. Please contact the salon." % cutoff)
    return {"appointment": booking.reschedule(a, d.get("date"), d.get("time"))}


@route("GET", "/api/my/reviews", "user")
def my_reviews(req):
    return db.all("SELECT r.*, sv.name AS service_name, st.name AS staff_name FROM reviews r LEFT JOIN services sv ON sv.id=r.service_id LEFT JOIN staff st ON st.id=r.staff_id WHERE r.user_id=? ORDER BY r.created DESC", (req.user["id"],))


# ---- direct chat with the salon ----
def conversation_for(uid):
    c = db.one("SELECT * FROM conversations WHERE user_id=?", (uid,))
    if not c:
        cid = db.run("INSERT INTO conversations(user_id,last_message_at) VALUES(?,?)", (uid, db.now_str()))
        c = db.one("SELECT * FROM conversations WHERE id=?", (cid,))
    return c


@route("GET", "/api/my/chat", "user")
def my_chat(req):
    if req.user["role"] != "customer":
        raise ApiError(403, "Staff replies from the Messages inbox.")
    c = conversation_for(req.user["id"])
    after = int(req.query.get("after", 0) or 0)
    msgs = db.all("SELECT id,sender,body,created FROM messages WHERE conversation_id=? AND id>? ORDER BY id", (c["id"], after))
    if c["customer_unread"]:
        db.run("UPDATE conversations SET customer_unread=0 WHERE id=?", (c["id"],))
    return {"messages": msgs}


@route("POST", "/api/my/chat", "user")
def my_chat_send(req):
    if req.user["role"] != "customer":
        raise ApiError(403, "Staff replies from the Messages inbox.")
    body = text(req.json(), "body", 1000, True, "Message")
    if security.rate_limited("chat:%d" % req.user["id"], 30, 300):
        raise ApiError(429, "You are sending messages very quickly. Please wait a moment.")
    c = conversation_for(req.user["id"])
    mid = db.run("INSERT INTO messages(conversation_id,sender,sender_user_id,body,created) VALUES(?,?,?,?,?)", (c["id"], "customer", req.user["id"], body, db.now_str()))
    db.run("UPDATE conversations SET admin_unread=admin_unread+1, archived=0, last_message_at=? WHERE id=?", (db.now_str(), c["id"]))
    notify.notify_admins("message", "New message from %s" % req.user["name"], body[:100], "#/admin/messages/%d" % c["id"], chat_only=True)
    return {"id": mid}


# ---- notifications (any signed-in user, including admin/staff) ----
@route("GET", "/api/notifications", "user")
def notifications(req):
    rows = db.all("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 60", (req.user["id"],))
    unread = db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (req.user["id"],))
    chat_unread = db.scalar("SELECT customer_unread FROM conversations WHERE user_id=?", (req.user["id"],)) or 0
    return {"notifications": rows, "unread": unread, "chat_unread": chat_unread}


@route("POST", "/api/notifications/read", "user")
def notifications_read(req):
    d = req.json()
    ids = d.get("ids")
    if ids:
        for i in ids[:100]:
            db.run("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (int(i), req.user["id"]))
    else:
        db.run("UPDATE notifications SET is_read=1 WHERE user_id=?", (req.user["id"],))
    return {"ok": True}
