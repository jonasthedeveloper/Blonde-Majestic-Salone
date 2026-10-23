# Blonde Majestic Ladies Salon — Booking & Management System

A self-contained salon system: a customer-facing website with an online booking wizard, chat and reviews, plus a full **owner/staff admin dashboard** with appointments, catalogue, revenue reporting and analytics — all backed by a single **SQLite** database.

**No third-party libraries are required.** The backend uses only the Python standard library (Python 3.9+).

---

## Features

**Customer website**
- Services, team, shop, promotions, reviews, gallery, location and contact pages
- Step-by-step **booking wizard** (services → date & time → details → confirmation) with live availability
- Customer accounts: profile, reschedule/cancel appointments, review history, notifications
- Salon chat (real staff) and a database-grounded AI assistant
- Mobile-first layout with bottom navigation and an installable web-app manifest

**Owner & staff dashboard** (`/#/admin`)
- Role-based access: owners get every section; staff see only their own appointments
- Appointment lifecycle: confirm, start, complete, record payment, refund, void, no-show, reschedule
- Catalogue management: categories, services, stylists, products, promotions
- **Revenue module** — income = *Paid* payments on *Completed* appointments − refunds, with CSV export and printable reports
- Analytics (booking heat map, trends), reviews moderation, testimonials, customer messaging inbox
- Settings: business info, opening hours, closures, booking rules, rating baseline, images, optional Twilio SMS

---

## Technology stack

| Layer     | Technology                                              |
|-----------|---------------------------------------------------------|
| Backend   | Python 3.9+ (standard library only), `http.server`      |
| Database  | SQLite (`data/salon.db`, created and seeded on first run) |
| Frontend  | Vanilla HTML / CSS / JavaScript single-page app (`public/`) |
| Tests     | Python end-to-end API tests; optional Playwright browser tests |

---

## Repository structure

```
blonde-majestic-salon/
├── server.py             # Web server entry point
├── app/                  # Backend modules
│   ├── config.py         # Environment-based configuration (.env)
│   ├── db.py             # SQLite schema, first-run seeding, helpers
│   ├── security.py       # Password hashing, sessions, CSRF, rate limiting
│   ├── booking.py        # Booking engine: availability, validation, references
│   ├── revenue.py        # Payments, refunds, income reports
│   ├── notify.py         # In-app notifications + optional Twilio SMS
│   ├── ai.py             # Database-grounded AI assistant
│   ├── uploads.py        # Image upload handling with type sniffing
│   ├── api_public.py     # Customer-facing API
│   ├── api_admin.py      # Owner/staff API (role-checked on every route)
│   └── web.py            # Static file / route serving helpers
├── public/               # Frontend SPA
│   ├── index.html
│   ├── css/styles.css
│   └── js/               # core, booking, customer, chat, admin, admin2, boot
├── data/                 # Runtime database + generated owner login file
│   └── .gitkeep          # folder tracked; contents are git-ignored
├── uploads/              # Uploaded photos (git-ignored; .gitkeep keeps folder)
├── tests/
│   ├── e2e.py            # End-to-end API test suite
│   ├── run.sh            # Runs API tests against a throwaway server/database
│   ├── ui.py             # Headless-browser test (Playwright)
│   └── run_ui.sh         # Runs the browser test suite
├── .env.example          # Configuration template (copy to .env)
├── start.bat             # Windows launcher
├── start.sh              # macOS / Linux launcher
└── README.md
```

---

## Prerequisites

- **Python 3.9 or newer** — <https://www.python.org/downloads/>
  *or* **[uv](https://docs.astral.sh/uv/)**, which downloads and manages a Python interpreter for you (no system install).
- Nothing else — there is **no `pip install` step** and no Node.js requirement.

---

## Installation & setup

1. Clone or download the repository.
2. *(Optional but recommended)* create your configuration file:
   - Windows: `copy .env.example .env`
   - macOS/Linux: `cp .env.example .env`
   - Every variable is optional; edit values as needed (see **Configuration** below).

### Starting the application

| Method | Command | Notes |
|---|---|---|
| Windows | `start.bat` | Double-click or run from a terminal |
| macOS / Linux | `./start.sh` | Requires `python3` on your PATH |
| Any OS with uv | `uv run --no-project python server.py` | No local Python installation needed |

Then open **<http://localhost:8000>**

- Customer website: `http://localhost:8000/`
- **Owner/staff dashboard:** `http://localhost:8000/#/admin`
- Testing from a phone: set `HOST=0.0.0.0` in `.env`, restart, and open `http://<your-computer-IP>:8000`

### First-run owner account (secure by design)

- On the very first run the system **generates** the owner login, prints it to the terminal **and** saves it to `data/FIRST-RUN-ADMIN-LOGIN.txt`.
- Sign in at `/#/admin`, change the password immediately under *Account → Settings*, then **delete** `data/FIRST-RUN-ADMIN-LOGIN.txt`.
- To choose the owner credentials up front, set `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env` **before the first run**. `.env` is listed in `.gitignore`, so credentials never enter the repository — never write real passwords into `.env.example`, the README, or any committed file.

---

## Configuration (`.env`)

Copy `.env.example` to `.env`; every variable is optional:

| Variable | Purpose | Default |
|---|---|---|
| `HOST` / `PORT` | Bind address and port (`0.0.0.0` to expose on your LAN) | `127.0.0.1` / `8000` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Owner account created on first run (leave `PASSWORD` empty to generate one) | — |
| `SECURE_COOKIES` | Set `1` when the site is served over HTTPS | `0` |
| `TZ_OFFSET_HOURS` | Salon timezone offset (Dubai = UTC+4) | `4` |
| `MAX_UPLOAD_MB` | Photo upload size limit | `5` |
| `REMINDER_HOURS` | Appointment reminder lead time | `24` |
| `SMS_ENABLED` + `TWILIO_*` | Optional Twilio SMS integration | disabled |
| `PAYMENT_GATEWAY` | No online gateway is connected | `none` |

Restart the server after changing `.env`.

---

## Automated tests

**API end-to-end suite** — starts its own throwaway server (port 8765) with a temporary database; it never touches your real data:

```bash
bash tests/run.sh
```

> Requires `python3` on your PATH. On Windows where `python3` is not available, run the equivalent with uv (works in Git Bash):
>
> ```bash
> rm -f bm_test.db*
> DB_PATH=bm_test.db PORT=8765 ADMIN_PASSWORD=TestPass123 uv run --no-project python server.py --quiet &
> uv run --no-project python tests/e2e.py http://localhost:8765 owner@salon.local TestPass123
> ```
>
> The test database file is git-ignored (`*.db`); delete it afterwards.

**Browser test suite** (optional; needs [Playwright](https://playwright.dev/python/)):

```bash
pip install playwright && playwright install chromium
bash tests/run_ui.sh
```

---

## Database & backups

- SQLite creates `data/salon.db` (plus `-wal` / `-shm` journal files) automatically on first run and seeds services, staff and settings.
- **All real data lives in `data/` and `uploads/` — both are deliberately git-ignored**, so the repository never contains customer information, photos or credentials. Their folder structure is preserved with `.gitkeep` files.
- Back up `data/` and `uploads/` regularly. Safest approach: **stop the server**, copy `data/salon.db*`, restart. For a live copy use `sqlite3 data/salon.db ".backup backup.db"`.
- Never commit the database, journal files or `FIRST-RUN-ADMIN-LOGIN.txt` (all ignored by `.gitignore`).

---

## Before going live — things only the salon can fill in

- **Prices**: no prices were invented. Services start as “Price on request” with a 60-minute placeholder duration. Set both in *Admin → Services*.
- **Stylists per service**: only assignments that follow the stated specialties are pre-filled (Elma→hair, Jopay→nails, Sumya→microshading & brow arts, Sharon/Rosie→foot spa). Lash, lash lift, microblading, facial and waxing have **no stylist yet** and can’t be booked online until you assign one (the dashboard warns you).
- **Facebook URL** (button hidden until set), **map coordinates** (pre-filled approximately for Al Rigga — verify in *Settings → Business*), optional Google Maps key.
- **Rating**: starts at 4.9 / 375+ as a baseline; real reviews are blended in automatically. Set the baseline to 0 in *Settings → Booking & rating* to use real reviews only.
- Cancellation/reschedule cut-off is 0 hours (no restriction) until you set one. No online payment gateway is connected; payments are recorded by the owner at checkout.
- Photos: the site ships without stock photos. Upload hero, gallery, staff, service, product and promotion images in the admin.

---

## Revenue rules

Income = payments that are **Paid** and whose appointment is **Completed**, minus refunds. Pending, voided, cancelled and no-show never count.
Discounts come from the promotion on the booking. Refund (full/partial) and void adjust totals instantly. Reports export to CSV or print.

---

## SMS (optional)

Set `SMS_ENABLED=1` and the three `TWILIO_*` values in `.env`. Without them everything works with in-app notifications.

---

## Security considerations & deployment notes

- Passwords hashed (**scrypt**), HttpOnly session cookies, CSRF header + same-origin checks, role checks on every admin API route, upload type sniffing (no SVG), rate limiting, CSP headers.
- **Deploy behind HTTPS** (e.g. a reverse proxy such as nginx or Caddy) and set `SECURE_COOKIES=1`.
- The built-in server is intended for local/LAN use; put a production WSGI-capable proxy or the provided server behind TLS before exposing it to the internet.
- Keep `.env`, `data/` and `uploads/` private — they are excluded from Git by design. The repository contains no real credentials.
- `.env.example` documents the *names* of configuration variables only; always keep real values out of version control.
