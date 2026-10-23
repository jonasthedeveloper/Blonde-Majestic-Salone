"""Configuration. Values come from environment variables or an optional .env file."""
import os, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_dotenv()


def env(key, default=""):
    return os.environ.get(key, default)


HOST = env("HOST", "127.0.0.1")          # use 0.0.0.0 to open the site from phones on your network
PORT = int(env("PORT", "8000"))
DATA_DIR = ROOT / "data"
UPLOAD_DIR = ROOT / "uploads"
PUBLIC_DIR = ROOT / "public"
DB_PATH = pathlib.Path(env("DB_PATH", str(DATA_DIR / "salon.db")))
TZ_OFFSET = float(env("TZ_OFFSET_HOURS", "4"))   # Dubai = UTC+4 (no daylight saving)
SESSION_DAYS = int(env("SESSION_DAYS", "14"))
SECURE_COOKIES = env("SECURE_COOKIES", "0") == "1"  # set to 1 when served over HTTPS
MAX_UPLOAD_MB = float(env("MAX_UPLOAD_MB", "5"))
REMINDER_HOURS = float(env("REMINDER_HOURS", "24"))

# First-run owner account (a random password is generated and printed if not provided)
ADMIN_EMAIL = env("ADMIN_EMAIL", "owner@salon.local")
ADMIN_PASSWORD = env("ADMIN_PASSWORD", "")

# SMS (Twilio). Leave blank to run with in-app notifications only.
SMS_ENABLED = env("SMS_ENABLED", "0") == "1"
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER")
SMS_DEFAULT_COUNTRY_CODE = env("SMS_DEFAULT_COUNTRY_CODE", "971")

# Payment gateway placeholder: no gateway is wired in. Payments are recorded by staff at the salon.
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "none")
