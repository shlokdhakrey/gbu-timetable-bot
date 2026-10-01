"""
TRY IT WITHOUT TELEGRAM
=======================
See the timetable logic working right in your terminal - no bot token needed.

    python try_it.py                      asks you a few questions
    python try_it.py BCS-I-A              today's classes for BCS-I-A
    python try_it.py BCS-I-A tuesday 1    Tuesday, lab batch 1
"""

import re
import sys
from datetime import datetime, timedelta
from html import unescape

import config
import messages
from timetable import DAY_NAMES, Timetable, simplify


def plain(html_text):
    """Remove Telegram's HTML tags so it prints nicely in a terminal."""
    return unescape(re.sub(r"<[^>]+>", "", html_text))


def ask(question, default=""):
    answer = input(f"{question} ").strip()
    return answer or default


def parse_day(word, now):
    word = word.lower()
    if word in ("", "today"):
        return now.isoweekday(), "today"
    if word == "tomorrow":
        return (now + timedelta(days=1)).isoweekday(), "tomorrow"
    for number, name in DAY_NAMES.items():
        if name.lower().startswith(word[:3]):
            return number, None
    sys.exit(f"Unknown day: {word!r}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # emojis on Windows too
    args = sys.argv[1:]
    tt = Timetable()
    tt.refresh()
    if not tt.rows:
        sys.exit("Couldn't load the timetable. Try: TIMETABLE_URL=sample_data/timetable_sample.json")

    name = args[0] if args else ask("Your class (e.g. BCS-I-A):")
    matches = tt.search_sections(name)
    if not matches:
        sys.exit(f"No class matches {name!r}")
    if len(matches) > 1 and simplify(matches[0][1]) != simplify(name):
        print("Did you mean one of these?", ", ".join(section for _, section in matches[:10]))
        return
    section_id, section = matches[0]
    info = tt.section_info(section_id)
    print(f"\n{section} - {info['program']} ({info['school']})")

    batches = tt.batches(section_id)
    if len(args) > 2:
        batch = int(args[2])
    elif batches and not args:
        batch = int(ask(f"Lab batches {batches} - which one? (Enter = all)", "0"))
    else:
        batch = 0

    if len(args) > 1:
        day_word = args[1]
    elif args:
        day_word = "today"
    else:
        day_word = ask("Day? (today/tomorrow/mon...sun)", "today")
    now = datetime.now(config.IST)
    day, when = parse_day(day_word, now)

    student = {"section_id": section_id, "section": section, "batch": batch}
    print()
    print(plain(messages.day_timetable(student, day, tt.classes_on(section_id, day, batch), when)))
    print("\n" + "─" * 40)
    running, date, upcoming = tt.next_classes(section_id, batch, now)
    print(plain(messages.next_class(student, now, running, date, upcoming)))


if __name__ == "__main__":
    main()
