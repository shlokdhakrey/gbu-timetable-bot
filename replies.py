"""
🧠  THE BRAIN
=============
Handles one Telegram "update" (a message, or a tap on a button).

Same steps as the n8n workflow:
    🧠 Understand message         → understand()
    👤 Find student               → students.get()
    🔀 What does the student want? → the ACTIONS table at the bottom
    one function per action       → show_schools(), save_class(), show_day(), ...
"""

from datetime import datetime, timedelta

import config
import messages
import students
import telegram_api as tg

# Typed commands → action names
COMMANDS = {
    "/start": "start", "/class": "start",
    "/today": "today", "/tomorrow": "tomorrow", "/next": "next", "/week": "week",
    "/stop": "stop", "/help": "help",
}

# Button taps carry short "callback data", e.g. "s:SOICT" or "c:1299"
CALLBACKS = {"home": "start", "s": "school", "p": "program", "c": "section", "b": "batch", "d": "day"}


def understand(update):
    """Turn a raw Telegram update into: who sent it, and what they want."""
    if "callback_query" in update:                       # a button was tapped
        tap = update["callback_query"]
        if "message" not in tap:
            return None
        kind, _, value = tap.get("data", "").partition(":")
        return {
            "chat_id": tap["message"]["chat"]["id"],
            "name": tap["from"].get("first_name", ""),
            "action": CALLBACKS.get(kind, "help"),
            "value": value,
            "callback_id": tap["id"],
            "message_id": tap["message"]["message_id"],  # so we can edit that message
        }

    message = update.get("message")
    if not message:
        return None
    text = (message.get("text") or "").strip()
    first_word = text.split()[0].split("@")[0].lower() if text else ""   # "/today@MyBot" → "/today"

    if text in messages.MENU_BUTTONS:
        action = messages.MENU_BUTTONS[text]
    elif first_word in COMMANDS:
        action = COMMANDS[first_word]
    elif text and not text.startswith("/"):
        action = "search"                                # maybe they typed their class name
    else:
        action = "help"

    return {
        "chat_id": message["chat"]["id"],
        "name": message.get("from", {}).get("first_name", ""),
        "action": action,
        "value": text,
        "callback_id": None,
        "message_id": None,
    }


def reply(who, text, buttons=None):
    """If they tapped a button, update that message in place. Otherwise send a new one."""
    if who["message_id"]:
        tg.edit_message(who["chat_id"], who["message_id"], text, buttons)
    else:
        tg.send_message(who["chat_id"], text, buttons=buttons)


# ── Picking a class: school → program → class → batch ─────────────────────

def show_schools(who, tt):
    reply(who, messages.pick_school(who["name"], who["student"]),
          messages.school_buttons(tt.schools()))


def show_programs(who, tt):
    school = who["value"]
    reply(who, messages.pick_program(school), messages.program_buttons(tt.programs(school)))


def show_sections(who, tt):
    sections = tt.sections(who["value"])
    if not sections:
        return show_schools(who, tt)
    info = tt.section_info(sections[0][0])
    reply(who, messages.pick_section(info["program"]),
          messages.section_buttons(sections, back=f"s:{info['school']}"))


def save_class(who, tt):
    info = tt.section_info(who["value"])
    if not info:
        return reply(who, messages.CLASS_GONE)
    student = students.save(who["chat_id"], name=who["name"], batch=0, **info)
    batches = tt.batches(info["section_id"])
    if batches:                                          # labs split into batches → ask which
        reply(who, messages.pick_batch(info["section"]), messages.batch_buttons(batches))
    else:
        finish_setup(who, student)


def save_batch(who, tt):
    if not who["student"]:
        return show_schools(who, tt)
    student = students.save(who["chat_id"], batch=int(who["value"] or 0))
    finish_setup(who, student)


def finish_setup(who, student):
    reply(who, messages.class_chosen(student))
    tg.send_message(who["chat_id"], messages.all_set(student), menu=messages.MENU)
    print(f"💾 {who['name'] or who['chat_id']} saved as {student['section']} (batch {student['batch']})")


def search(who, tt):
    matches = tt.search_sections(who["value"])[:12]
    if matches:
        tg.send_message(who["chat_id"], messages.search_results(who["value"]),
                        buttons=messages.section_buttons(matches))
    else:
        tg.send_message(who["chat_id"], messages.no_match(who["value"]))


# ── Showing the timetable ─────────────────────────────────────────────────

def show_day(who, tt):
    student = who["student"]
    if not student:
        return tg.send_message(who["chat_id"], messages.NOT_REGISTERED)
    now = datetime.now(config.IST)
    if who["action"] == "today":
        day, when = now.isoweekday(), "today"
    elif who["action"] == "tomorrow":
        day, when = (now + timedelta(days=1)).isoweekday(), "tomorrow"
    else:                                                # a day button from /week
        day, when = int(who["value"] or 0), None
        if day not in range(1, 8):
            day = now.isoweekday()
    classes = tt.classes_on(student["section_id"], day, student.get("batch", 0))
    text = messages.day_timetable(student, day, classes, when)
    if who["action"] == "day":
        reply(who, text, messages.day_buttons())         # keep the day buttons, like tabs
    else:
        tg.send_message(who["chat_id"], text)


def show_next(who, tt):
    student = who["student"]
    if not student:
        return tg.send_message(who["chat_id"], messages.NOT_REGISTERED)
    now = datetime.now(config.IST)
    running, date, upcoming = tt.next_classes(student["section_id"], student.get("batch", 0), now)
    tg.send_message(who["chat_id"], messages.next_class(student, now, running, date, upcoming))


def show_week(who, tt):
    if not who["student"]:
        return tg.send_message(who["chat_id"], messages.NOT_REGISTERED)
    tg.send_message(who["chat_id"], messages.PICK_DAY, buttons=messages.day_buttons())


# ── Everything else ───────────────────────────────────────────────────────

def stop(who, tt):
    students.remove(who["chat_id"])
    tg.send_message(who["chat_id"], messages.GOODBYE, remove_menu=True)


def show_help(who, tt):
    tg.send_message(who["chat_id"], messages.HELP)


ACTIONS = {
    "start": show_schools, "school": show_programs, "program": show_sections,
    "section": save_class, "batch": save_batch, "search": search,
    "today": show_day, "tomorrow": show_day, "day": show_day,
    "next": show_next, "week": show_week, "stop": stop, "help": show_help,
}


def handle_update(update, tt):
    who = understand(update)
    if who is None:
        return                                           # e.g. an edited message: ignore
    if who["callback_id"]:
        tg.answer_callback(who["callback_id"])           # stops the button's loading spinner
    who["student"] = students.get(who["chat_id"])
    print(f"💬 {who['name'] or who['chat_id']}: {who['action']} {who['value']}".rstrip())

    if not tt.rows and who["action"] not in ("stop", "help"):
        return tg.send_message(who["chat_id"], messages.NO_TIMETABLE)
    ACTIONS.get(who["action"], show_help)(who, tt)
