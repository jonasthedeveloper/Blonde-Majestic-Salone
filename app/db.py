"""SQLite access layer, schema and first-run master data."""
import sqlite3, threading, json, contextlib, secrets, datetime as dt
from . import config

_local = threading.local()
_cache = {"settings": None}


def conn():
    c = getattr(_local, "c", None)
    if c is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(config.DB_PATH), isolation_level=None, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.c = c
    return c


def all(sql, a=()):
    return [dict(r) for r in conn().execute(sql, a).fetchall()]


def one(sql, a=()):
    r = conn().execute(sql, a).fetchone()
    return dict(r) if r else None


def scalar(sql, a=()):
    r = conn().execute(sql, a).fetchone()
    return r[0] if r else None


def run(sql, a=()):
    return conn().execute(sql, a).lastrowid


@contextlib.contextmanager
def tx():
    c = conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except BaseException:
        c.execute("ROLLBACK")
        raise


def now_str():
    n = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=config.TZ_OFFSET)
    return n.strftime("%Y-%m-%d %H:%M:%S")


# ---- settings (key/value JSON) ----
def settings():
    if _cache["settings"] is None:
        _cache["settings"] = {r["key"]: json.loads(r["value"]) for r in all("SELECT key,value FROM settings")}
    return _cache["settings"]


def setting(key, default=None):
    return settings().get(key, default)


def set_setting(key, value):
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)))
    _cache["settings"] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, role TEXT NOT NULL CHECK(role IN('admin','staff','customer')),
 name TEXT NOT NULL, email TEXT UNIQUE, phone TEXT, password_hash TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, can_chat INTEGER NOT NULL DEFAULT 0, staff_id INTEGER, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '', image TEXT DEFAULT '', sort INTEGER DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id), name TEXT NOT NULL,
 description TEXT DEFAULT '', price REAL, duration_min INTEGER, image TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1, avail_days TEXT DEFAULT '[0,1,2,3,4,5,6]', sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT DEFAULT '', bio TEXT DEFAULT '', image TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS staff_services(staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE, service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE, PRIMARY KEY(staff_id,service_id));
CREATE TABLE IF NOT EXISTS staff_hours(staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE, weekday INTEGER NOT NULL, start TEXT, "end" TEXT, off INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(staff_id,weekday));
CREATE TABLE IF NOT EXISTS blocks(id INTEGER PRIMARY KEY, staff_id INTEGER REFERENCES staff(id) ON DELETE CASCADE, date_from TEXT NOT NULL, date_to TEXT NOT NULL, start_time TEXT DEFAULT '', end_time TEXT DEFAULT '', reason TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS product_categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, category_id INTEGER REFERENCES product_categories(id) ON DELETE SET NULL, name TEXT NOT NULL, description TEXT DEFAULT '', price REAL, stock INTEGER DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created TEXT);
CREATE TABLE IF NOT EXISTS product_images(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE, filename TEXT NOT NULL, caption TEXT DEFAULT '', sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS promotions(id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '', image TEXT DEFAULT '', discount_type TEXT NOT NULL DEFAULT 'percent', discount_value REAL NOT NULL DEFAULT 0,
 service_ids TEXT DEFAULT '[]', requires_all INTEGER NOT NULL DEFAULT 0, start_date TEXT DEFAULT '', end_date TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created TEXT);
CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, ref TEXT UNIQUE NOT NULL, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, customer_name TEXT NOT NULL, customer_phone TEXT NOT NULL, customer_email TEXT DEFAULT '',
 date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','confirmed','in_progress','completed','cancelled','no_show')),
 customer_notes TEXT DEFAULT '', admin_notes TEXT DEFAULT '', promo_id INTEGER REFERENCES promotions(id) ON DELETE SET NULL, source TEXT DEFAULT 'online', reminded INTEGER DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_appt_date ON appointments(date);
CREATE TABLE IF NOT EXISTS appointment_items(id INTEGER PRIMARY KEY, appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE, service_id INTEGER REFERENCES services(id) ON DELETE SET NULL, service_name TEXT NOT NULL,
 category_id INTEGER, staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL, date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, price REAL);
CREATE INDEX IF NOT EXISTS ix_item_staff_date ON appointment_items(staff_id,date);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, appointment_id INTEGER UNIQUE NOT NULL REFERENCES appointments(id) ON DELETE CASCADE, gross REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, net REAL NOT NULL,
 method TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','paid','refunded','voided')), paid_at TEXT, recorded_by INTEGER, refunded_amount REAL NOT NULL DEFAULT 0, reason TEXT DEFAULT '', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, author_name TEXT NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), body TEXT DEFAULT '', image TEXT DEFAULT '',
 service_id INTEGER REFERENCES services(id) ON DELETE SET NULL, staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL, featured INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1, verified INTEGER NOT NULL DEFAULT 0, source TEXT DEFAULT 'customer', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE, archived INTEGER NOT NULL DEFAULT 0, last_message_at TEXT, admin_unread INTEGER NOT NULL DEFAULT 0, customer_unread INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, sender TEXT NOT NULL CHECK(sender IN('customer','salon')), sender_user_id INTEGER, body TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_knowledge(id INTEGER PRIMARY KEY, keywords TEXT NOT NULL, answer TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, type TEXT NOT NULL, title TEXT NOT NULL, body TEXT DEFAULT '', link TEXT DEFAULT '', is_read INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_notif_user ON notifications(user_id,is_read);
CREATE TABLE IF NOT EXISTS sms_log(id INTEGER PRIMARY KEY, to_number TEXT, body TEXT, status TEXT, detail TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS password_resets(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL, expires TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_reset_token ON password_resets(token_hash);
CREATE INDEX IF NOT EXISTS ix_reset_user ON password_resets(user_id);
"""

DEFAULT_SETTINGS = {
    "business_name": "Blonde Majestic Ladies Salon",
    "tagline": "Beauty, confidence and elegance, made for her.",
    "description": "Blonde Majestic Ladies Salon is an exclusive ladies beauty salon in Al Rigga, Deira, Dubai. "
                   "We offer hair, nail, lash, brow, skin and body-care services in a comfortable and welcoming environment.",
    "business_type": "Women-owned / Exclusive Ladies Beauty Salon",
    "owner_name": "Jally Concepcion", "owner_title": "Owner", "owner_bio": "", "owner_image": "",
    "address": "Al Rigga Rd, Al Muraqqabat, Deira, Dubai, United Arab Emirates",
    "area": "Al Rigga, Deira, Dubai",
    "phone": "+971 50 579 9758", "email": "", "website": "blondemajesticladiessalon.com", "facebook_url": "",
    "hours": [{"day": d, "open": "10:00", "close": "22:00", "closed": False}
              for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]],
    "amenities": ["Free Wi-Fi", "Wheelchair Accessibility", "Beverages", "Free Parking"],
    "payment_methods": ["Credit Cards", "Debit Cards", "NFC Mobile Payments", "Apple Pay", "Google Pay"],
    "hero_image": "", "gallery": [],
    "map_lat": 25.2654, "map_lng": 55.3238, "google_maps_key": "",
    "baseline_rating": 4.9, "baseline_count": 375,
    "default_duration": 60, "slot_step": 30, "min_notice_minutes": 0, "booking_horizon_days": 60,
    "customer_change_cutoff_hours": 0, "auto_confirm": False,
    "appointment_policy": "Appointments are recommended. Please book ahead to secure your preferred stylist and time.",
    "payment_methods_record": ["Cash", "Credit Card", "Debit Card", "NFC Mobile Payment", "Apple Pay", "Google Pay"],
}

CATALOG = [
    ("Hair Care & Styling", ["Hair Coloring / Highlights / Bleaching", "Hair Treatments", "Brazilian Keratin", "Rebonding", "Hair Cut", "Hair Styling", "Blowdry"]),
    ("Nail Care / Nail Spa", ["Classic Manicure", "Classic Pedicure", "Gelish Polish", "Nail Art", "Foot Spa", "Soft Gel Extensions", "Acrylic Extensions"]),
    ("Lashes & Brows", ["Classic Eyelash Extensions", "Lash Lifts", "Microblading", "Microshading", "Brow Arts"]),
    ("Skin & Body Care", ["Rejuvenating Facial Treatments", "Precise Waxing Services"]),
]
STAFF = [("Elma", "Hair Magic, Treatments & Styling"), ("Jopay", "Nail Care & Extensions"), ("Sumya", "Microshading & Brow Arts"),
         ("Sharon", "Foot Spa & Massage"), ("Rosie", "Foot Spa & Body Pampering")]
# Only assignments that follow directly from the stated specialties are pre-filled. Admin completes the rest.
ASSIGN = {
    "Elma": ["Hair Coloring / Highlights / Bleaching", "Hair Treatments", "Brazilian Keratin", "Rebonding", "Hair Cut", "Hair Styling", "Blowdry"],
    "Jopay": ["Classic Manicure", "Classic Pedicure", "Gelish Polish", "Nail Art", "Soft Gel Extensions", "Acrylic Extensions"],
    "Sumya": ["Microshading", "Brow Arts"],
    "Sharon": ["Foot Spa"], "Rosie": ["Foot Spa"],
}
PRODUCT_CATS = ["Hair Care", "Nail Care", "Skin Care", "Beauty", "Accessories", "Salon Recommended"]


def init():
    conn().executescript(SCHEMA)
    # Migration: CREATE TABLE IF NOT EXISTS is a no-op on databases created before a column existed.
    if "image" not in [r["name"] for r in all("PRAGMA table_info(categories)")]:
        run("ALTER TABLE categories ADD COLUMN image TEXT DEFAULT ''")
    for k, v in DEFAULT_SETTINGS.items():   # add missing keys only; never overwrite admin edits
        if k not in settings():
            set_setting(k, v)
    if scalar("SELECT COUNT(*) FROM categories") == 0:
        sid = {}
        for ci, (cat, svcs) in enumerate(CATALOG):
            cid = run("INSERT INTO categories(name,sort) VALUES(?,?)", (cat, ci))
            for si, s in enumerate(svcs):
                sid[s] = run("INSERT INTO services(category_id,name,duration_min,sort) VALUES(?,?,?,?)",
                             (cid, s, setting("default_duration", 60), si))
        for i, (n, sp) in enumerate(STAFF):
            st = run("INSERT INTO staff(name,specialty,sort) VALUES(?,?,?)", (n, sp, i))
            for s in ASSIGN.get(n, []):
                run("INSERT INTO staff_services VALUES(?,?)", (st, sid[s]))
        for i, n in enumerate(PRODUCT_CATS):
            run("INSERT INTO product_categories(name,sort) VALUES(?,?)", (n, i))
    if scalar("SELECT COUNT(*) FROM users WHERE role='admin'") == 0:
        from . import security
        pw = config.ADMIN_PASSWORD or secrets.token_urlsafe(9)
        run("INSERT INTO users(role,name,email,phone,password_hash,can_chat,created) VALUES('admin',?,?,?,?,1,?)",
            (setting("owner_name"), config.ADMIN_EMAIL.lower(), setting("phone"), security.hash_password(pw), now_str()))
        if not config.ADMIN_PASSWORD:
            note = f"Owner login created on first run\nEmail: {config.ADMIN_EMAIL}\nPassword: {pw}\nChange it after signing in (Account > Settings). Delete this file afterwards.\n"
            (config.DATA_DIR / "FIRST-RUN-ADMIN-LOGIN.txt").write_text(note)
            print("\n" + "=" * 60 + "\n" + note + "=" * 60 + "\n")
