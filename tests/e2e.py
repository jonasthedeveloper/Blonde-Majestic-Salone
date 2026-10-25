"""End-to-end API test. Start the server on another port with a throw-away DB, then run:  python3 tests/e2e.py http://localhost:8765 owner@salon.local TestPass123"""
import sys, json, urllib.request, urllib.error, http.cookiejar, datetime as dt, uuid

BASE, ADMIN_EMAIL, ADMIN_PW = sys.argv[1:4]
fails = 0


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, path, data=None, raw=None, ctype=None, hdr=True):
        if isinstance(data, bytes):  # multipart: call(method, path, *multipart(...))
            body, ctype = data, raw
        else:
            body = json.dumps(data).encode() if data is not None else None
        r = urllib.request.Request(BASE + path, data=body, method=method)
        if hdr:
            r.add_header("X-Requested-With", "fetch")
        r.add_header("Content-Type", ctype or "application/json")
        try:
            with self.op.open(r) as resp:
                b = resp.read()
                return resp.status, (json.loads(b) if resp.headers.get("Content-Type", "").startswith("application/json") else b)
        except urllib.error.HTTPError as e:
            b = e.read()
            try:
                return e.code, json.loads(b)
            except Exception:
                return e.code, b


def check(name, cond, info=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> %s" % (info,)))
    fails += 0 if cond else 1


def multipart(fields, files):
    b = "----" + uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode()
    for k, fn, data in files:
        out += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n' % (b, k, fn)).encode() + data + b"\r\n"
    out += ("--%s--\r\n" % b).encode()
    return out, "multipart/form-data; boundary=" + b


PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")

anon, cust, admin = Client(), Client(), Client()
s, d = anon.call("GET", "/api/public")
check("public bootstrap", s == 200 and len(d["categories"]) == 4 and len(d["staff"]) == 5, d if s != 200 else "")
check("initial rating baseline 4.9/375", d["rating"]["average"] == 4.9 and d["rating"]["total"] == 375, d["rating"])
s, svcs = anon.call("GET", "/api/services")
by = {x["name"]: x for x in svcs}
check("services seeded (21)", len(svcs) == 21, len(svcs))
hair = by["Hair Cut"]
check("Hair Cut staff = Elma", [x["name"] for x in hair["staff"]] == ["Elma"])

# auth + access control
s, _ = anon.call("GET", "/api/admin/dashboard")
check("anon blocked from admin", s == 401)
s, _ = anon.call("POST", "/api/book", {}, hdr=False)
check("CSRF header required", s == 403)
s, r = cust.call("POST", "/api/auth/register", {"name": "Test Customer", "email": "t@example.com", "phone": "+971 50 111 2222", "password": "secret123"})
check("customer register", s == 200 and r["user"]["role"] == "customer", r)
s, _ = cust.call("GET", "/api/admin/dashboard")
check("customer blocked from admin (403)", s == 403)
s, r = admin.call("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PW})
check("admin login", s == 200 and r["user"]["role"] == "admin", r)
s, r = anon.call("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": "wrong"})
check("bad password rejected", s == 401)

# availability + booking
tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
s, av = anon.call("POST", "/api/availability", {"date": tomorrow, "items": [{"service_id": hair["id"], "staff_id": None}]})
check("availability returns slots 10:00..", s == 200 and av["slots"][0]["time"] == "10:00" and av["slots"][-1]["time"] == "21:00", av if s != 200 else av["slots"][-1])
body = {"customer_name": "Test Customer", "customer_phone": "+971501112222", "date": tomorrow, "time": "10:00", "items": [{"service_id": hair["id"]}]}
s, b1 = cust.call("POST", "/api/book", body)
check("booking created (pending)", s == 200 and b1["appointment"]["status"] == "pending", b1)
s, b2 = anon.call("POST", "/api/book", dict(body, customer_name="Other Guest"))
check("double booking blocked (409)", s == 409, (s, b2))
s, av = anon.call("POST", "/api/availability", {"date": tomorrow, "items": [{"service_id": hair["id"]}]})
check("booked time removed from slots", "10:00" not in [x["time"] for x in av["slots"]] and "09:30" not in [x["time"] for x in av["slots"]])
s, _ = anon.call("POST", "/api/book", dict(body, time="09:00"))
check("outside hours rejected", s in (400, 409))
s, _ = anon.call("POST", "/api/book", dict(body, time="21:30"))
check("ends after closing rejected", s == 409, s)
s, r = anon.call("POST", "/api/book", dict(body, customer_phone="abc"))
check("bad phone rejected", s == 400, r)
facial = by["Rejuvenating Facial Treatments"]
s, r = anon.call("POST", "/api/book", dict(body, items=[{"service_id": facial["id"]}], time="12:00"))
check("service with no staff cannot be booked online", s == 400, r)
# multi-service sequential booking (hair + nail)
nail = by["Gelish Polish"]
s, r = anon.call("POST", "/api/book", dict(body, customer_name="Multi", time="12:00", items=[{"service_id": hair["id"]}, {"service_id": nail["id"]}]))
check("multi-service booking, sequential times", s == 200 and [i["start_time"] for i in r["appointment"]["items"]] == ["12:00", "13:00"], r)
# admin block
s, r = admin.call("POST", "/api/admin/blocks", {"date_from": tomorrow, "date_to": tomorrow, "start_time": "16:00", "end_time": "18:00", "reason": "Staff meeting", "staff_id": ""})
check("admin block created", s == 200, r)
s, r = anon.call("POST", "/api/book", dict(body, time="16:30", customer_name="Blocked"))
check("blocked time unavailable", s == 409, r)
admin.call("DELETE", "/api/admin/blocks/%d" % r.get("id", 0)) if False else None

# admin appointment flow + revenue
aid = b1["appointment"]["id"]
s, r = admin.call("PUT", "/api/admin/appointments/%d" % aid, {"status": "confirmed"})
check("admin confirms", s == 200 and r["status"] == "confirmed", r)
s, n = cust.call("GET", "/api/notifications")
check("customer got booking notifications", s == 200 and n["unread"] >= 2, n)
s, r = admin.call("PUT", "/api/admin/appointments/%d" % aid, {"status": "completed"})
check("cannot complete without payment endpoint", s == 400)
s, r = admin.call("POST", "/api/admin/appointments/%d/complete" % aid, {"method": "Cash"})
check("complete requires price when unpriced", s == 400, r)
s, r = admin.call("POST", "/api/admin/services/%d" % hair["id"], None) if False else (0, 0)
s, r = admin.call("PUT", "/api/admin/services/%d" % hair["id"], {"category_id": hair["category_id"], "name": hair["name"], "price": 100, "duration_min": 60, "active": 1, "staff_ids": [x["id"] for x in hair["staff"]]})
check("admin sets service price", s == 200 and r["price"] == 100, r)
s, pr = admin.call("POST", "/api/admin/promotions", {"title": "Birthday Beauty", "discount_type": "percent", "discount_value": 10, "service_ids": [], "active": 1})
check("promotion created", s == 200, pr)
s, r = admin.call("POST", "/api/admin/appointments/%d/complete" % aid, {"items": [{"id": b1["appointment"]["items"][0]["id"], "price": 200}], "promo_id": pr["id"], "method": "Credit Card", "paid": True})
p = r.get("payment") if s == 200 else None
check("complete + pay: gross 200, discount 20, net 180", p and (p["gross"], p["discount"], p["net"], p["status"]) == (200, 20, 180, "paid"), r)
s, rev = admin.call("GET", "/api/admin/revenue?preset=today")
check("revenue today = 180", s == 200 and rev["cards"]["today"]["income"] == 180 and rev["filtered"]["totals"]["transactions"] == 1, rev["cards"] if s == 200 else rev)
# a cancelled / no-show never counts
mid = r["id"] if False else None
sid = None
s, ap = admin.call("GET", "/api/admin/appointments?status=pending")
other = [a for a in ap if a["customer_name"] == "Multi"][0]
s, r = admin.call("PUT", "/api/admin/appointments/%d" % other["id"], {"status": "no_show"})
check("no-show set", s == 200 and r["status"] == "no_show", r)
s, rev = admin.call("GET", "/api/admin/revenue")
check("no-show not in income", rev["cards"]["all"]["income"] == 180)
# refund adjusts income
s, _ = admin.call("POST", "/api/admin/payments/%d/refund" % p["id"], {"amount": 30, "reason": "Partial"})
s, rev = admin.call("GET", "/api/admin/revenue")
check("partial refund reduces income to 150", rev["cards"]["all"]["income"] == 150, rev["cards"]["all"])
s, _ = admin.call("POST", "/api/admin/payments/%d/void" % p["id"], {"reason": "Mistake"})
s, rev = admin.call("GET", "/api/admin/revenue")
check("void removes income", rev["cards"]["all"]["income"] == 0 and rev["filtered"]["transactions"][0]["status"] == "voided", rev["cards"]["all"])
s, csvb = admin.call("GET", "/api/admin/revenue/report?format=csv")
check("CSV export", s == 200 and b"Total gross service amount" in csvb)
s, rev = admin.call("GET", "/api/admin/revenue?preset=custom&from=2020-01-01&to=2020-01-31&method=Cash")
check("custom range/method filter works", s == 200 and rev["filtered"]["totals"]["income"] == 0)

# customer cancel / appointments
s, mine = cust.call("GET", "/api/my/appointments")
check("customer sees own appointments", s == 200 and len(mine["appointments"]) >= 1)
s, r = anon.call("POST", "/api/book", dict(body, time="14:00", customer_name="Cancel Me"))
# staff can't see others
# chat
s, r = cust.call("POST", "/api/my/chat", {"body": "Hi, available po ba si Elma tomorrow?"})
check("customer sends chat", s == 200, r)
s, cv = admin.call("GET", "/api/admin/conversations")
check("admin inbox lists conversation (unread)", s == 200 and len(cv) == 1 and cv[0]["admin_unread"] == 1, cv)
s, _ = admin.call("POST", "/api/admin/conversations/%d/reply" % cv[0]["id"], {"body": "Yes po!"})
s, m = cust.call("GET", "/api/my/chat")
check("customer receives reply", len(m["messages"]) == 2 and m["messages"][1]["sender"] == "salon")
s, n = cust.call("GET", "/api/notifications")
check("customer notified of admin reply", any(x["type"] == "message" for x in n["notifications"]))
s, n = admin.call("GET", "/api/notifications")
check("admin notified of message", any(x["type"] == "message" for x in n["notifications"]))
# AI
for q, must in (("Open ba kayo Sunday?", "every Sunday from 10:00 AM to 10:00 PM"), ("What are your hours?", "10:00 AM to 10:00 PM"), ("How much is hair cut?", "Price: AED 100"),
                ("magkano gelish polish", "has not published a price"), ("where are you located", "Al Rigga"), ("do you take cash?", "don't have information"),
                ("who is Sumya", "Microshading"), ("available po ba si Elma tomorrow?", "Elma"), ("blorp zzz", "don't have that information")):
    s, a = anon.call("POST", "/api/ai-chat", {"message": q})
    check("AI: %s" % q, s == 200 and must in a["reply"], a)
# reviews
s, r = cust.call("POST", "/api/reviews", *multipart({"rating": "5", "body": "Excellent service and very accommodating staff."}, [("image", "x.png", PNG)]))
check("review w/ image saved", s == 200, r)
s, rr = anon.call("GET", "/api/reviews")
check("rating recalculated with real review", rr["summary"]["total"] == 376 and rr["summary"]["real_total"] == 1 and rr["summary"]["average"] == 4.9, rr["summary"])
s, bad = cust.call("POST", "/api/reviews", *multipart({"rating": "5", "body": "hello there"}, [("image", "x.png", b"<svg onload=alert(1)>")]))
check("non-image upload rejected", s == 400, bad)
# products + multiple images
s, pc = anon.call("GET", "/api/product-categories")
s, prod = admin.call("POST", "/api/admin/products", {"name": "Argan Oil", "price": 55, "stock": 4, "category_id": pc[0]["id"], "active": 1})
check("product created", s == 200, prod)
s, r = admin.call("POST", "/api/admin/products/%d/images" % prod["id"], *multipart({}, [("f", "a.png", PNG), ("f", "b.png", PNG), ("f", "c.png", PNG)]))
check("multiple product images", s == 200 and len(r["images"]) == 3, r)
s, pub = anon.call("GET", "/api/products/%d" % prod["id"])
check("public product shows 3 images", len(pub["images"]) == 3)
s, img = anon.call("GET", "/uploads/" + pub["images"][0]["filename"])
check("uploaded image is served", s == 200 and img[:4] == b"\x89PNG")
s, r = anon.call("GET", "/uploads/../data/salon.db")
check("path traversal blocked", s == 404)
# settings + staff login role
s, r = admin.call("PUT", "/api/admin/settings", {"phone": "+971 50 579 9758", "hours": [{"open": "10:00", "close": "22:00", "closed": False}] * 7})
check("settings update", s == 200, r)
s, st = admin.call("GET", "/api/admin/staff")
elma = [x for x in st if x["name"] == "Elma"][0]
s, r = admin.call("POST", "/api/admin/staff/%d/login" % elma["id"], {"email": "elma@example.com", "password": "elmapass99", "can_chat": False})
check("staff login created", s == 200, r)
staffc = Client()
s, r = staffc.call("POST", "/api/auth/login", {"email": "elma@example.com", "password": "elmapass99"})
s, ap = staffc.call("GET", "/api/admin/appointments")
check("staff sees only own appointments", s == 200 and all(any(i["staff_name"] == "Elma" for i in a["items"]) for a in ap) and len(ap) > 0)
s, _ = staffc.call("GET", "/api/admin/revenue")
check("staff blocked from revenue", s == 403)
s, _ = staffc.call("GET", "/api/admin/conversations")
check("staff without chat permission blocked", s == 403)
s, dash = admin.call("GET", "/api/admin/dashboard")
check("dashboard loads", s == 200 and dash["counts"]["staff"] == 5, dash if s != 200 else "")
s, an = admin.call("GET", "/api/admin/analytics")
check("analytics loads", s == 200 and an["total"] >= 1)
# service category images (mirrors the service image pattern: upload -> filename -> save -> persist -> remove)
s, r = admin.call("POST", "/api/admin/upload", *multipart({}, [("f", "cat.png", PNG)]))
check("category image uploaded", s == 200 and len(r["filenames"]) == 1, r)
catimg = r["filenames"][0]
s, cats = admin.call("GET", "/api/admin/categories")
cid = cats[0]["id"]
base = {"name": cats[0]["name"], "description": cats[0]["description"], "sort": cats[0]["sort"], "active": 1}
s, r = admin.call("PUT", "/api/admin/categories/%d" % cid, dict(base, image=catimg))
check("category image saved", s == 200 and r["image"] == catimg, r)
s, r = admin.call("GET", "/api/admin/categories")
check("category image persists on reload", r[0]["image"] == catimg, r[0])
s, pub = anon.call("GET", "/api/public")
check("public categories carry image", any(c.get("image") == catimg for c in pub["categories"]))
s, up = anon.call("GET", "/uploads/" + catimg)
check("category image served", s == 200 and up[:4] == b"\x89PNG")
s, r = admin.call("PUT", "/api/admin/categories/%d" % cid, dict(base, image=""))
check("category image removed", s == 200 and r["image"] == "", r)
s, r = admin.call("PUT", "/api/admin/categories/%d" % cid, dict(base, image="../../evil.png"))
check("invalid category image rejected", s == 400, r)
s, r = anon.call("GET", "/api/services")
check("services still fine after category change", s == 200 and len(r) == 21, len(r))
print("\n%d failure(s)" % fails)
sys.exit(1 if fails else 0)
