"""
THE CLOCK
=========
bot.py calls tick() every few seconds. Each time, it asks two questions:

  Is it time for the morning summary?          (config.MORNING_SUMMARY_AT)
  Does a class start in the next few minutes?  (config.REMIND_MINUTES_BEFORE)

It writes down what it already sent in data/sent.json, so even if the bot
restarts, nobody gets the same message twice.

In the n8n workflow this is the "Every 5 minutes" trigger, followed by
"Anything due now?" and "Build summary / reminders".
"""

import json
import math
import os
import time
from datetime import datetime, timedelta

import requests

import config
import messages
import students
import telegram_api as tg
from timetable import at_time, period_times

SENT_FILE = os.path.join(config.DATA_DIR, "sent.json")


# ── Remembering what we already sent today ────────────────────────────────

def _load_sent(today):
    try:
        with open(SENT_FILE, encoding="utf-8") as f:
            sent = json.load(f)
    except (OSError, ValueError):
        sent = {}
    if sent.get("date") != today:          # a new day: start with a clean list
        sent = {"date": today, "done": []}
    return sent


def _mark_sent(sent, key):
    sent["done"].append(key)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent, f)


# ── Sending ───────────────────────────────────────────────────────────────

def deliver(chat_id, text):
    """Send one automatic message. Returns True if it arrived."""
    try:
        tg.send_message(chat_id, text)
        time.sleep(0.05)                   # be gentle: Telegram allows ~30 messages/second
        return True
    except tg.TelegramError as error:
        if error.code == 403:              # the student blocked the bot -> stop messaging them
            students.remove(chat_id)
        print(f"Could not message {chat_id}: {error}")
    except requests.RequestException as error:
        print(f"Could not message {chat_id}: {error}")
    return False


def send_morning_summaries(tt, now):
    day, sent = now.isoweekday(), 0
    for chat_id, student in students.everyone():
        classes = tt.classes_on(student["section_id"], day, student.get("batch", 0))
        if classes:                        # no classes today -> don't disturb them
            sent += deliver(chat_id, messages.morning_summary(student, day, classes))
    print(f"Morning summaries sent: {sent}")


def send_class_reminders(tt, now, period):
    day, sent = now.isoweekday(), 0
    for chat_id, student in students.everyone():
        # Only classes that START in this period (not the 2nd hour of a lab)
        classes = [c for c in tt.classes_on(student["section_id"], day, student.get("batch", 0))
                   if c["first_period"] == period]
        if classes:
            minutes_left = math.ceil((at_time(now.date(), classes[0]["start"]) - now).total_seconds() / 60)
            sent += deliver(chat_id, messages.reminder(student, classes, minutes_left))
    if sent:
        print(f"Reminders sent for period {period}: {sent}")


# ── The tick ──────────────────────────────────────────────────────────────

def tick(tt, now=None):
    now = now or datetime.now(config.IST)
    today = now.date()
    sent = _load_sent(today.isoformat())

    # Morning summary: any time in the hour after MORNING_SUMMARY_AT, once a day
    summary_time = at_time(today, config.MORNING_SUMMARY_AT)
    if summary_time <= now < summary_time + timedelta(hours=1) and "summary" not in sent["done"]:
        _mark_sent(sent, "summary")        # write it down first, so a crash can't cause repeats
        send_morning_summaries(tt, now)

    # Class reminders: from X minutes before a period starts until it starts
    periods_today = sorted({r["period"] for r in tt.rows if r["day"] == now.isoweekday()})
    for period in periods_today:
        class_start = at_time(today, period_times(period)[0])
        remind_from = class_start - timedelta(minutes=config.REMIND_MINUTES_BEFORE)
        key = f"period-{period}"
        if remind_from <= now < class_start and key not in sent["done"]:
            _mark_sent(sent, key)
            send_class_reminders(tt, now, period)
