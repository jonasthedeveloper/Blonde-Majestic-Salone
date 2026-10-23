"""Salon assistant. Answers ONLY from the salon's own database (settings, services, staff, promotions, admin FAQ entries).
It never invents prices, services, schedules or policies; when it does not know, it says so and points to the salon."""
import re, datetime as dt, json
from . import db
from .booking import Day, now_local, t12, mm, hm, chain

DAYS = {"monday": 0, "mon": 0, "lunes": 0, "tuesday": 1, "tue": 1, "tues": 1, "martes": 1, "wednesday": 2, "wed": 2, "miyerkules": 2,
        "thursday": 3, "thu": 3, "thurs": 3, "huwebes": 3, "friday": 4, "fri": 4, "biyernes": 4, "saturday": 5, "sat": 5, "sabado": 5,
        "sunday": 6, "sun": 6, "linggo": 6}
STOP = {"and", "the", "a", "of", "care", "services", "service", "treatments", "for", "my", "me", "do", "you", "have", "is", "are", "ba", "po", "ang", "mga", "kayo", "how", "much", "what", "price", "of", "magkano", "with"}


def words(msg):
    return re.findall(r"[a-zñ0-9']+", msg.lower().replace("á", "a").replace("é", "e"))


def hours_text(i):
    h = db.setting("hours")[i]
    return "closed" if h.get("closed") else "%s to %s" % (t12(h["open"]), t12(h["close"]))


def money(v):
    return "AED %s" % ("%d" % v if float(v).is_integer() else "%.2f" % v)


def contact_line():
    return "You can call us at %s or tap “Chat with Salon” to message the team." % db.setting("phone")


def find_services(ws):
    svcs = db.all("SELECT s.*, c.name AS cat FROM services s JOIN categories c ON c.id=s.category_id WHERE s.active=1 AND c.active=1")
    msg = " ".join(ws)
    best, scored = 0, []
    for s in svcs:
        toks = [t.rstrip("s") for t in words(s["name"]) if t not in STOP and len(t) > 2]
        if not toks:
            continue
        if s["name"].lower() in msg:
            sc = 1.5
        else:
            hit = sum(1 for t in toks if any(t == w.rstrip("s") or (len(t) > 4 and w.rstrip("s").startswith(t[:5])) for w in ws))
            sc = hit / len(toks)
        if sc >= 0.5:
            scored.append((sc, s))
            best = max(best, sc)
    return [s for sc, s in scored if sc == best] if scored else []


def service_answer(s, want_price=False):
    price = money(s["price"]) if s["price"] is not None else None
    parts = ["%s (%s)." % (s["name"], s["cat"])]
    if s["description"]:
        parts.append(s["description"])
    parts.append("Price: %s." % price if price else "Price: the salon has not published a price for this service yet. Please contact the salon for a quote.")
    if s["duration_min"]:
        parts.append("Estimated duration: %d minutes." % s["duration_min"])
    staff = db.all("SELECT st.name FROM staff st JOIN staff_services ss ON ss.staff_id=st.id WHERE ss.service_id=? AND st.active=1", (s["id"],))
    if staff:
        parts.append("Available with: %s." % ", ".join(x["name"] for x in staff))
    return " ".join(parts), [{"label": "View %s" % s["name"], "href": "#/services/%d" % s["id"]}, {"label": "Book this service", "href": "#/book?service=%d" % s["id"]}]


def target_date(ws):
    today = now_local().date()
    if "tomorrow" in ws or "bukas" in ws:
        return today + dt.timedelta(days=1)
    if "today" in ws or "ngayon" in ws:
        return today
    for w in ws:
        if w in DAYS:
            delta = (DAYS[w] - today.weekday()) % 7
            return today + dt.timedelta(days=delta)
    return None


def answer(message):
    msg = (message or "").strip()[:500]
    ws = words(msg)
    wset = set(ws)
    name = db.setting("business_name")
    act_book = [{"label": "Book an appointment", "href": "#/book"}]

    # 1. admin-managed FAQ entries
    low = msg.lower()
    for k in db.all("SELECT * FROM ai_knowledge WHERE active=1"):
        kws = [x.strip().lower() for x in k["keywords"].split(",") if x.strip()]
        if any(x in low for x in kws):
            return {"reply": k["answer"], "actions": []}

    staff = db.all("SELECT * FROM staff WHERE active=1 ORDER BY sort,id")
    named = [s for s in staff if s["name"].lower() in wset]
    d = target_date(ws)

    # 2. staff availability (reads the live schedule)
    if named and (wset & {"available", "free", "avail", "slot", "slots", "open", "tomorrow", "bukas", "today", "ngayon"} or d):
        d = d or now_local().date()
        s = named[0]
        day = Day(d)
        dur = int(db.setting("default_duration", 60))
        step = max(5, int(db.setting("slot_step", 30)))
        times = []
        if day.win:
            now = now_local()
            for st in range(day.win[0], day.win[1] - dur + 1, step):
                if d == now.date() and st < now.hour * 60 + now.minute:
                    continue
                if day.free(s["id"], st, st + dur):
                    times.append(t12(mm(st)))
        label = d.strftime("%A, %d %b")
        if not day.win:
            return {"reply": "The salon is closed on %s (%s)." % (label, day.closed_reason or ""), "actions": []}
        if not times:
            return {"reply": "%s has no open times on %s based on the live schedule. You can try another day, or message the salon team to ask." % (s["name"], label),
                    "actions": [{"label": "Chat with Salon", "href": "#/chat/salon"}] + act_book}
        return {"reply": "Yes, %s has openings on %s, for example %s%s. Times depend on the service length, so please pick your service in the booking page to see exact times." %
                (s["name"], label, ", ".join(times[:5]), " and more" if len(times) > 5 else ""), "actions": act_book}

    # 3. price / specific service
    svc = find_services(ws)
    if wset & {"price", "prices", "cost", "magkano", "rate", "rates", "fee", "fees", "pricing"} or "how much" in low:
        if len(svc) == 1:
            r, a = service_answer(svc[0], True)
            return {"reply": r, "actions": a}
        if len(svc) > 1:
            return {"reply": "Which one do you mean? " + ", ".join(s["name"] for s in svc[:6]) + ". Tap a service to see its price.", "actions": [{"label": s["name"], "href": "#/services/%d" % s["id"]} for s in svc[:4]]}
        return {"reply": "Prices are set per service and shown on each service page. Tell me which service you are interested in, or browse the list. I only quote prices the salon has published.", "actions": [{"label": "Browse services", "href": "#/services"}]}

    # 4. hours
    if wset & {"open", "opens", "close", "closes", "closing", "hours", "oras", "bukas", "sarado", "schedule", "time", "late"} or (wset & set(DAYS) and not named):
        if wset & set(DAYS):
            i = DAYS[[w for w in ws if w in DAYS][0]]
            h = db.setting("hours")[i]
            if h.get("closed"):
                return {"reply": "The salon is closed on %ss." % h["day"], "actions": []}
            return {"reply": "Yes! %s is open every %s from %s." % (name, h["day"], hours_text(i)), "actions": act_book}
        hrs = db.setting("hours")
        same = all(not h.get("closed") and h["open"] == hrs[0]["open"] and h["close"] == hrs[0]["close"] for h in hrs)
        if same:
            txt = "%s is open Monday to Sunday, %s to %s." % (name, t12(hrs[0]["open"]), t12(hrs[0]["close"]))
        else:
            txt = "Our hours: " + "; ".join("%s %s" % (h["day"], hours_text(i)) for i, h in enumerate(hrs)) + "."
        return {"reply": txt + " " + db.setting("appointment_policy", ""), "actions": act_book}

    # 5. location
    if wset & {"where", "location", "address", "saan", "nasaan", "map", "direction", "directions", "located", "find", "parking"}:
        if "parking" in wset:
            am = db.setting("amenities", [])
            has = any("parking" in a.lower() for a in am)
            return {"reply": ("Yes, we offer %s." % [a for a in am if "parking" in a.lower()][0]) if has else "I don't have parking information. " + contact_line(), "actions": []}
        return {"reply": "We are at %s." % db.setting("address"), "actions": [{"label": "Open map", "href": "#/location"}]}

    # 6. contact
    if wset & {"phone", "call", "number", "contact", "whatsapp", "facebook", "website", "email", "reach"}:
        bits = ["Phone: %s" % db.setting("phone")]
        if db.setting("website"):
            bits.append("Website: %s" % db.setting("website"))
        if db.setting("facebook_url"):
            bits.append("Facebook: %s" % db.setting("facebook_url"))
        return {"reply": "You can reach us here. " + ". ".join(bits) + ".", "actions": [{"label": "Chat with Salon", "href": "#/chat/salon"}, {"label": "Contact", "href": "#/contact"}]}

    # 7. promotions
    if wset & {"promo", "promos", "promotion", "promotions", "discount", "discounts", "deal", "deals", "package", "packages", "offer", "offers", "birthday"}:
        today = now_local().date().isoformat()
        ps = db.all("SELECT * FROM promotions WHERE active=1 AND (start_date='' OR start_date<=?) AND (end_date='' OR end_date>=?)", (today, today))
        if not ps:
            return {"reply": "There are no active promotions listed right now. Check back soon, or ask the salon team.", "actions": [{"label": "Chat with Salon", "href": "#/chat/salon"}]}
        return {"reply": "Current promotions: " + "; ".join(p["title"] for p in ps[:5]) + ". Open the promotions page for details.", "actions": [{"label": "View promotions", "href": "#/promotions"}]}

    # 8. payments
    if wset & {"pay", "payment", "payments", "card", "cards", "apple", "google", "nfc", "cash", "gcash", "bayad"}:
        pm = db.setting("payment_methods", [])
        txt = "We accept: %s." % ", ".join(pm)
        if "cash" in wset or "gcash" in wset:
            txt += " I don't have information about other payment methods, so please confirm with the salon. " + contact_line()
        return {"reply": txt, "actions": []}

    # 9. amenities
    if wset & {"wifi", "wi-fi", "wheelchair", "beverage", "beverages", "drinks", "amenities", "facilities"}:
        return {"reply": "Our amenities: %s." % ", ".join(db.setting("amenities", [])), "actions": []}

    # 10. booking / appointment questions
    if wset & {"book", "booking", "appointment", "appointments", "reserve", "reservation", "magpa", "cancel", "reschedule", "resched", "walk", "walkin"} or "walk-in" in low or "walk in" in low:
        if wset & {"cancel", "reschedule", "resched"}:
            c = float(db.setting("customer_change_cutoff_hours", 0) or 0)
            rule = " Changes are accepted at least %g hours before your appointment." % c if c else ""
            return {"reply": "You can cancel or reschedule from Account > Appointments.%s If you booked without an account, please contact the salon." % rule, "actions": [{"label": "My appointments", "href": "#/account/appointments"}, {"label": "Chat with Salon", "href": "#/chat/salon"}]}
        pre = ""
        if svc and len(svc) == 1:
            return {"reply": "Great choice! Tap below to book %s." % svc[0]["name"], "actions": [{"label": "Book " + svc[0]["name"], "href": "#/book?service=%d" % svc[0]["id"]}]}
        return {"reply": "Booking takes about a minute: choose your service(s), your preferred stylist (or any available), a date and time, then confirm. " + db.setting("appointment_policy", ""), "actions": act_book}

    # 11. rating / reviews
    if wset & {"rating", "reviews", "review", "rated", "stars"}:
        from .api_public import rating_summary
        r = rating_summary()
        return {"reply": "Our guests rate us %.1f / 5 from %d reviews." % (r["average"], r["total"]), "actions": [{"label": "Read reviews", "href": "#/reviews"}]}

    # 12. staff
    if named:
        s = named[0]
        sv = db.all("SELECT sv.name FROM services sv JOIN staff_services ss ON ss.service_id=sv.id WHERE ss.staff_id=? AND sv.active=1", (s["id"],))
        txt = "%s: %s." % (s["name"], s["specialty"])
        if sv:
            txt += " Services booked with %s: %s." % (s["name"], ", ".join(x["name"] for x in sv[:8]))
        return {"reply": txt, "actions": [{"label": "Meet the team", "href": "#/staff"}] + act_book}
    if wset & {"staff", "stylist", "stylists", "team", "who", "beautician", "technician"}:
        return {"reply": "Our team: " + "; ".join("%s (%s)" % (s["name"], s["specialty"]) for s in staff) + ".", "actions": [{"label": "Meet the team", "href": "#/staff"}]}

    # 13. services
    if svc and len(svc) == 1:
        r, a = service_answer(svc[0])
        return {"reply": r, "actions": a}
    if svc:
        return {"reply": "I found: " + ", ".join(s["name"] for s in svc[:6]) + ". Which one would you like to know about?", "actions": [{"label": s["name"], "href": "#/services/%d" % s["id"]} for s in svc[:4]]}
    if wset & {"service", "services", "offer", "menu", "hair", "nail", "nails", "lash", "lashes", "brow", "brows", "skin", "facial", "wax", "waxing", "massage", "body"}:
        cats = db.all("SELECT c.name, COUNT(s.id) n FROM categories c LEFT JOIN services s ON s.category_id=c.id AND s.active=1 WHERE c.active=1 GROUP BY c.id ORDER BY c.sort,c.id")
        return {"reply": "We offer: " + "; ".join("%s (%d services)" % (c["name"], c["n"]) for c in cats) + ".", "actions": [{"label": "Browse services", "href": "#/services"}]}

    if wset & {"hi", "hello", "hey", "good", "kumusta", "kamusta", "hola"} and len(ws) <= 4:
        return {"reply": "Hello! Welcome to %s. I can help with hours, services, prices, our team, promotions and booking. What would you like to know?" % name, "actions": act_book}
    if wset & {"thanks", "thank", "salamat", "ty"}:
        return {"reply": "You're welcome! We look forward to seeing you.", "actions": []}

    return {"reply": "I'm sorry, I don't have that information. " + contact_line(), "actions": [{"label": "Chat with Salon", "href": "#/chat/salon"}]}
