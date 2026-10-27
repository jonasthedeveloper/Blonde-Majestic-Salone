# Blonde Majestic Ladies Salon — Booking & Management System

A salon booking and management system with a customer-facing website, online appointment booking, customer accounts, chat, reviews, and an owner/staff administration dashboard.

The backend uses Python's standard library, and the application stores its data in a local SQLite database.

## Features

### Customer Website
- Browse salon services, team members, products, promotions, reviews, and gallery.
- Book appointments using a step-by-step booking wizard.
- View appointment availability.
- Manage customer profiles and appointments.
- View review history and notifications.
- Use the salon chat and AI assistant.
- Mobile-friendly interface with an installable web-app manifest.

### Owner and Staff Dashboard

Open the dashboard at `http://localhost:8000/#/admin`.

- Role-based owner and staff access.
- Manage appointments, confirmations, cancellations, rescheduling, and payments.
- Manage service categories, services, stylists, products, and promotions.
- Track revenue and generate reports.
- Review booking analytics and moderate reviews.
- Manage customer messages.
- Configure business details, opening hours, booking rules, and other settings.
- Optional Twilio SMS integration.

### Revenue Rules
Revenue is calculated from payments marked as **Paid** for appointments marked as **Completed**, minus refunds. Pending, cancelled, voided, and no-show appointments are excluded.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.9+ |
| Web server | Python standard library `http.server` |
| Database | SQLite |
| Frontend | HTML, CSS, and JavaScript |
| Tests | Python end-to-end tests and optional Playwright tests |

No third-party Python packages are required to run the basic application.

## Project Structure

```text
blonde-majestic-salon/
├── app/                 # Backend modules
├── data/                # Local database and generated login file
├── public/               # Frontend website assets
│   ├── css/
│   └── js/
├── tests/                # Automated tests
├── uploads/              # Uploaded images and files
├── .env.example          # Configuration template
├── .gitignore            # Excludes private and generated files
├── README.md             # Project documentation
├── .github/workflows/    # Auto-deploy to PythonAnywhere on push
├── server.py             # Local development entry point
├── wsgi_app.py           # Production entry point (WSGI, used by PythonAnywhere)
├── start.bat             # Windows launcher
└── start.sh              # macOS/Linux launcher
```

## Requirements

- Python 3.9 or newer, or [uv](https://docs.astral.sh/uv/) to manage a Python interpreter.
- Git is required if you want to clone the repository or contribute changes.

## Installation and Setup

### 1. Get the project

Clone the repository or download the project files from GitHub.

### 2. Optional environment configuration

Create a local `.env` file from the example:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Edit `.env` if you need to configure the application. Keep real passwords, tokens, and other secrets out of Git.

### 3. Start the application

**Windows:**

```powershell
.\start.bat
```

Alternatively, run:

```powershell
uv run --no-project python server.py
```

**macOS/Linux:**

```bash
./start.sh
```

Keep the terminal open while the server is running.

### 4. Open the website

- Customer website: [http://localhost:8000](http://localhost:8000)
- Owner/staff dashboard: [http://localhost:8000/#/admin](http://localhost:8000/#/admin)

## First-Run Owner Account

On the first run, the application generates owner login credentials and displays them in the terminal. It also saves them to:

```text
data/FIRST-RUN-ADMIN-LOGIN.txt
```

Sign in to the admin dashboard and change the generated password immediately. Delete the generated login file after securely recording the credentials.

You can configure the owner email and password before the first run using the environment variables supported by the application. Never commit real credentials or passwords.

## Configuration

Configuration is managed through environment variables in `.env`. The example file documents the supported variable names.

Depending on your configuration, available settings include:

- `HOST` and `PORT` — server address and port.
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` — initial owner account settings.
- `SECURE_COOKIES` — cookie security when using HTTPS.
- `TZ_OFFSET_HOURS` — salon timezone offset.
- `MAX_UPLOAD_MB` — upload size limit.
- `REMINDER_HOURS` — appointment reminder timing.
- `SMS_ENABLED` and `TWILIO_*` — optional SMS integration.
- `PAYMENT_GATEWAY` — payment gateway configuration.

Restart the server after changing environment settings. Check `app/config.py` and `.env.example` for the exact options supported by your version of the application.

## Automated Tests

The project includes an end-to-end API test suite and optional browser-based tests.

Run the API tests in an environment with the required shell tools:

```bash
bash tests/run.sh
```

The optional UI tests use Playwright. Install and configure Playwright according to its official documentation before running the browser test suite.

## Database and Backups

The application creates its SQLite database in the `data/` directory when it first runs. Uploaded images and files are stored in `uploads/`.

**Important:**
- Back up the database and uploaded files regularly.
- Keep customer records, appointment data, uploaded files, and login credentials private.
- Do not commit database files, generated login files, or private uploads to GitHub.
- The `.gitignore` file is intended to exclude local data and secrets from version control.

## Before Going Live

Review and configure the following in the admin dashboard:

- Service prices and appointment durations.
- Stylist assignments for each service.
- Business contact information and location.
- Opening hours and booking rules.
- Promotions, gallery images, and staff photos.
- Review rating settings and cancellation rules.
- SMS settings, if you intend to use SMS notifications.

Verify all business details before accepting real bookings.

## Free Cloud Hosting (PythonAnywhere)

The live site runs in the cloud, so it stays online when the laptop is off. The local
server and Cloudflare Tunnel are now development-only tools.

**Why PythonAnywhere's free tier instead of Render's free tier:**

- Render's free filesystem is *ephemeral* — every redeploy or restart would delete the
  SQLite database and the uploaded images, and Render's free Postgres expires after 30
  days and then deletes its data.
- PythonAnywhere's free account has a persistent 512 MiB home directory (the database
  and images live there), free HTTPS, no credit card, no time-limited trial, and the web
  app keeps running without a laptop.

**Free-tier limitations to be aware of:**

- No credit card, and the plan is free rather than a trial.
- One web worker: concurrent visitors queue behind each other.
- A web app unused for one month expires — log into PythonAnywhere at least monthly and
  extend the app. Visits and crawler traffic do **not** count as use.
- Free plan is username.pythonanywhere.com only (no custom domain).
- Production is served through `wsgi_app.py`; `server.py` remains the local dev server.

### One-time setup

1. Create a free account at <https://www.pythonanywhere.com/registration/register/beginner/>.
2. Dashboard → **Add a new web app** → *Manual configuration* → Python 3.12 (or the newest 3.x).
3. On the **Web** tab, click **WSGI configuration file** and replace its contents with:

   ```python
   import sys
   sys.path.insert(0, "/home/<username>/Blonde-Majestic-Salone")
   from wsgi_app import application
   ```

4. In a PythonAnywhere **Bash console**:

   ```bash
   cd ~ && git clone https://github.com/jonasthedeveloper/Blonde-Majestic-Salone.git
   ```

5. Upload the live data **once** — it is deliberately not in git: copy `data/salon.db`
   and everything in `uploads/` into `~/Blonde-Majestic-Salone/` (Files tab, drag & drop).
   After that they persist across restarts, reloads and every future deploy.
6. On the Web tab enable **Redirect HTTP to HTTPS** (needed because production runs with
   `SECURE_COOKIES=1`), then click **Reload**. The site answers at
   `https://<username>.pythonanywhere.com`.

### Automatic deployment from GitHub

[.github/workflows/deploy.yml](.github/workflows/deploy.yml) deploys every push to `main`.
Add these repository secrets (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `PA_USERNAME` | your PythonAnywhere username |
| `PA_API_TOKEN` | PythonAnywhere → Account → API token |
| `PA_DOMAIN` | e.g. `username.pythonanywhere.com` |

Workflow: VS Code → `git push` → GitHub → upload + reload → live site.
Deploys upload only *tracked* files, so the live database and uploaded images are never
overwritten (and production `.env` settings are created only if they do not exist yet).

### Optional: serve static files directly

For faster page loads, add these static file mappings on the Web tab so images and assets
do not consume the single free worker (paths assume the clone in the home directory):

- `/uploads/` → `/home/<username>/Blonde-Majestic-Salone/uploads/`
- `/css/` → `/home/<username>/Blonde-Majestic-Salone/public/css/`
- `/js/` → `/home/<username>/Blonde-Majestic-Salone/public/js/`
- `/favicon.svg` → `/home/<username>/Blonde-Majestic-Salone/public/favicon.svg`
- `/manifest.webmanifest` → `/home/<username>/Blonde-Majestic-Salone/public/manifest.webmanifest`

### Laptop offline test

With the setup above, all of these hold: laptop off, VS Code closed, XAMPP stopped and
Cloudflare Tunnel stopped — the site stays hosted because it runs on PythonAnywhere's
servers. [start-public.bat](start-public.bat) remains only for sharing a *local* build.

## Security and Deployment

- Keep `.env`, the database, uploaded files, and generated login credentials private.
- Use strong passwords and change the generated owner password immediately.
- For a public deployment, use HTTPS and configure secure cookies appropriately.
- Review the security, hosting, and backup configuration before exposing the application to the internet.
- The built-in Python server is primarily intended for local development and LAN use. Production deployment requires appropriate hosting and security configuration.

## License

No license has been specified for this project yet. Add a license if you intend to define permissions for others to reuse or distribute the code.
