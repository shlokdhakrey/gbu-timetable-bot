"""
WHAT THE BOT SAYS
=================
Every message text and button layout lives here, so you can change the
bot's words without touching the logic.

Telegram understands a little HTML: <b>bold</b>, <i>italic</i>, <code>code</code>.
"""

from html import escape

import config
from timetable import DAY_NAMES, at_time

# The menu that replaces the phone keyboard once a student has picked a class.
# Tapping a button simply sends its text, e.g. "Today".
MENU_BUTTONS = {
    "Today": "today",
    "Tomorrow": "tomorrow",
    "Next class": "next",
    "Week": "week",
    "Change class": "start",
}
MENU = [["Today", "Tomorrow"], ["Next class", "Week"], ["Change class"]]


def e(value):
    """Escape text so names like 'AI&ML' don't break Telegram's HTML."""
    return escape(str(value), quote=False)


def rows_of(buttons, per_row):
    """Split a flat list of buttons into rows: [a,b,c,d] -> [[a,b,c],[d]]."""
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def who(student):
    text = e(student["section"])
    if student.get("batch"):
        text += f", Batch {student['batch']}"
    return text


# ── Picking a class ───────────────────────────────────────────────────────

def pick_school(name, student=None):
    hello = f"Hi {e(name)}! " if name else "Hi! "
    text = hello + ("I'm the <b>GBU Timetable Bot</b>.\n"
                    "I'll send you your timetable every morning and remind you before every class.\n\n")
    if student and student.get("section"):
        text += f"You're currently in <b>{who(student)}</b>. Pick again to change it.\n\n"
    return text + "<b>Step 1 of 3</b>: which school are you in?"


def pick_program(school):
    return f"<b>Step 2 of 3</b>: your program in <b>{e(school)}</b>?"


def pick_section(program):
    return f"<b>Step 3 of 3</b>: your class in <b>{e(program)}</b>?"


def pick_batch(section):
    return (f"<b>{e(section)}</b> saved!\n\n"
            "Labs in your class are split into batches.\n<b>Which batch are you in?</b>")


def school_buttons(schools):
    return rows_of([(s, f"s:{s}") for s in schools], 3)


def program_buttons(programs):
    return [[(name, f"p:{program_id}")] for program_id, name in programs] + [[("Back", "home")]]


def section_buttons(sections, back=None):
    rows = rows_of([(name, f"c:{section_id}") for section_id, name in sections], 3)
    return rows + ([[("Back", back)]] if back else [])


def batch_buttons(batches):
    return rows_of([(f"Batch {b}", f"b:{b}") for b in batches], 3) + [[("Not sure, show all", "b:0")]]


def class_chosen(student):
    return f"Class chosen: <b>{who(student)}</b>"


def all_set(student):
    hour, minute = config.MORNING_SUMMARY_AT.split(":")
    return (f"<b>All set!</b> You're in <b>{who(student)}</b>\n"
            f"<i>{e(student['program'])}, {e(student['school'])}</i>\n\n"
            "I'll message you:\n"
            f"- every morning at {int(hour)}:{minute} with the day's classes\n"
            f"- {config.REMIND_MINUTES_BEFORE} minutes before each class\n\n"
            "Use the buttons below anytime.")


def search_results(text):
    return f'Classes matching "{e(text)}" - tap yours:'


def no_match(text):
    return (f'I couldn\'t find a class called "{e(text)}".\n\n'
            "Tap /start to pick it from a list, or /help to see what I can do.")


# ── Showing classes ───────────────────────────────────────────────────────

def class_card(c, show_batch=True):
    """
    One class, like:
        09:30-10:30 - Lecture
        Problem Solving Using C
        CSE101 - Shubh Laxmi - IL-104 (CLT)
    """
    header = f"<b>{c['start']}-{c['end']}</b> - {e(c['type'])}"
    if show_batch and c["batch"]:
        header += f" (Batch {c['batch']})"
    details = [f"<code>{e(c['code'])}</code>"] if c["code"] else []
    if c["teacher"]:
        details.append(e(c["teacher"]))
    if c["room"]:
        details.append(e(c["room"]))
    lines = [header, e(c["subject"])]
    if details:
        lines.append(" - ".join(details))
    return "\n".join(lines)


def cards(student, classes):
    # If the student chose a batch we only show their labs, so no need to label them.
    return "\n\n".join(class_card(c, show_batch=not student.get("batch")) for c in classes)


def day_timetable(student, day, classes, when=None):
    """The whole day. `when` is an optional word like "today" shown after the day name."""
    title = f"<b>{DAY_NAMES[day]}</b>" + (f" ({when})" if when else "") + f" - {who(student)}"
    if not classes:
        return f"{title}\n\nNo classes!"
    parts = [title]
    busy_until = None
    for c in classes:
        if busy_until and c["start"] > busy_until:
            parts.append(f"<i>Free {busy_until}-{c['start']}</i>")
        parts.append(class_card(c, show_batch=not student.get("batch")))
        busy_until = max(busy_until or c["end"], c["end"])
    return "\n\n".join(parts)


def describe_when(now, start):
    """'in 25 min', 'today at 14:30', 'tomorrow at 09:30' or 'on Monday at 09:30'."""
    minutes = int((start - now).total_seconds() // 60)
    days = (start.date() - now.date()).days
    if days == 0:
        if minutes < 60:
            return f"in {max(minutes, 1)} min ({start:%H:%M})"
        return f"today at {start:%H:%M}"
    if days == 1:
        return f"tomorrow at {start:%H:%M}"
    return f"on {DAY_NAMES[start.isoweekday()]} at {start:%H:%M}"


def next_class(student, now, running, date, upcoming):
    parts = []
    if running:
        parts.append(f"<b>Right now</b>\n{cards(student, running)}")
    if upcoming:
        start = at_time(date, upcoming[0]["start"])
        parts.append(f"<b>Next class</b> - {describe_when(now, start)}\n{cards(student, upcoming)}")
    if not parts:
        return f"No classes in the next 7 days for {who(student)}."
    return "\n\n".join(parts)


def day_buttons():
    days = [(DAY_NAMES[d][:3], f"d:{d}") for d in range(1, 8)]
    return [days[:4], days[4:]]


PICK_DAY = "Which day do you want to see?"


# ── Automatic messages ────────────────────────────────────────────────────

def reminder(student, classes, minutes):
    title = f"<b>Class in {minutes} minutes!</b>" if minutes > 1 else "<b>Class starting now!</b>"
    return f"{title}\n\n{cards(student, classes)}"


def morning_summary(student, day, classes):
    name = student.get("name") or "there"
    return f"<b>Good morning, {e(name)}!</b> Here's your day:\n\n" + day_timetable(student, day, classes)


# ── Other replies ─────────────────────────────────────────────────────────

HELP = ("<b>GBU Timetable Bot</b>\n"
        "I send your class timetable and remind you before every class.\n\n"
        "/start - choose your class\n"
        "/today - today's classes\n"
        "/tomorrow - tomorrow's classes\n"
        "/next - your next class\n"
        "/week - pick any day\n"
        "/stop - stop all messages\n\n"
        "You can also just type your class name, like <code>BCS-I-A</code>.")

NOT_REGISTERED = "You haven't picked your class yet.\nTap /start to choose it."

GOODBYE = "Done, I've forgotten your class and won't message you.\nTap /start anytime to come back."

CLASS_GONE = "That class isn't in the timetable anymore. Tap /start to pick again."

NO_TIMETABLE = "I couldn't load the timetable from mygbu.in right now. Please try again in a few minutes."
