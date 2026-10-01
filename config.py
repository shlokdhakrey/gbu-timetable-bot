"""
SETTINGS
========
Everything you might want to change lives in this one file.

Your secret bot token does NOT go here. Put it in a file called `.env`
(copy `.env.example`) so it never ends up on GitHub.
"""

import os
from datetime import timedelta, timezone


def _load_env_file(path=".env"):
    """Read KEY=value lines from .env into os.environ (a tiny python-dotenv)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


# ── Telegram ──────────────────────────────────────────────────────────────
# Get a token from @BotFather on Telegram and put it in .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Leave this alone. (Tests point it at a fake Telegram server.)
TELEGRAM_API = os.getenv("TELEGRAM_API", "https://api.telegram.org")


# ── Where the timetable comes from ────────────────────────────────────────
# These are the same URLs the mygbu.in website calls (we found them in the
# browser's Network tab / HAR file). We try them in order.
# You can also give a file path here, e.g. sample_data/timetable_sample.json,
# to run the bot with no internet access to mygbu.in.
TIMETABLE_SOURCES = [
    os.getenv("TIMETABLE_URL", "https://mygbu.in/schd/api.php"),  # live data
    "https://samay.mygbu.in/api.php",                              # backup mirror
]

# How often to download a fresh copy (in minutes). Downloading is ~3 MB,
# so we keep a copy in memory and on disk instead of downloading every time.
TIMETABLE_REFRESH_MINUTES = int(os.getenv("TIMETABLE_REFRESH_MINUTES", "180"))


# ── Time ──────────────────────────────────────────────────────────────────
# India has no daylight-saving time, so a fixed +05:30 offset is always right.
IST = timezone(timedelta(hours=5, minutes=30), "IST")

# Period number -> (start, end).
# Same rule as the mygbu.in website: period 1 starts 08:30, each lasts 1 hour.
# If your college's bell timings are different, just edit this table.
PERIODS = {
    1: ("08:30", "09:30"),
    2: ("09:30", "10:30"),
    3: ("10:30", "11:30"),
    4: ("11:30", "12:30"),
    5: ("12:30", "13:30"),
    6: ("13:30", "14:30"),
    7: ("14:30", "15:30"),
    8: ("15:30", "16:30"),
    9: ("16:30", "17:30"),
    10: ("17:30", "18:30"),
    11: ("18:30", "19:30"),
}


# ── When the bot messages students ────────────────────────────────────────
MORNING_SUMMARY_AT = os.getenv("MORNING_SUMMARY_AT", "07:30")   # daily timetable
REMIND_MINUTES_BEFORE = int(os.getenv("REMIND_MINUTES_BEFORE", "10"))


# ── Files ─────────────────────────────────────────────────────────────────
DATA_DIR = os.getenv("DATA_DIR", "data")   # students.json, cache, etc.
