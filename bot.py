"""
GBU TIMETABLE BOT - start here!
===============================
Run it with:   python bot.py

What happens:
  1. Download the timetable from mygbu.in              -> timetable.py
  2. Then, forever:
       a. Ask Telegram "any new messages?" (max 20 s)   -> telegram_api.py
       b. Reply to each message or button tap           -> replies.py
       c. Check the clock: summary or reminder due?     -> reminders.py

Asking Telegram again and again like this is called "long polling".
The n8n version uses a webhook instead: Telegram pushes every message to n8n.
"""

import sys
import time
import traceback

import requests

import config
import reminders
import replies
import telegram_api as tg
from timetable import Timetable


def connect():
    """Check the token works, and make sure no webhook is stealing our messages."""
    if ":" not in config.TELEGRAM_BOT_TOKEN:
        sys.exit("No bot token found.\n"
                 "   1. On Telegram, talk to @BotFather and send /newbot\n"
                 "   2. Copy .env.example to .env and paste the token into it")
    try:
        me = tg.call("getMe")
    except tg.TelegramError as error:
        sys.exit(f"Telegram didn't accept the token ({error.description}). Check your .env file.")
    print(f"Logged in as @{me['username']}")

    if tg.call("getWebhookInfo").get("url"):
        # Telegram sends messages EITHER to a webhook (like n8n) OR to getUpdates, never both.
        print("This bot was connected to a webhook (n8n?). Removing it so this program gets the messages.\n"
              "   Tip: create one bot for n8n and another one for this Python version.")
        tg.call("deleteWebhook")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # emojis on Windows too
    connect()
    tt = Timetable()
    tt.refresh()
    print("Bot is running! Message it on Telegram. Press Ctrl+C to stop.\n")

    offset = None                        # tells Telegram which updates we've already seen
    while True:
        try:
            for update in tg.get_updates(offset):
                offset = update["update_id"] + 1
                try:
                    replies.handle_update(update, tt)
                except Exception:
                    traceback.print_exc()    # one bad message must never kill the bot

            tt.refresh_if_old()              # new copy of the timetable every few hours
            reminders.tick(tt)               # summaries and reminders

        except KeyboardInterrupt:
            print("\nBot stopped.")
            break
        except (requests.RequestException, tg.TelegramError) as error:
            print(f"Connection problem ({error}). Trying again in 5 s...")
            time.sleep(5)
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
