"""
✅  TESTS — run with:   python -m unittest discover tests -v

They use the offline sample (sample_data/timetable_sample.json) and a fake
Telegram, so they work without internet and without a bot token.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DATA_DIR"] = tempfile.mkdtemp()          # never touch the real data/ folder

import config            # noqa: E402  (imports must come after DATA_DIR is set)
import reminders         # noqa: E402
import replies           # noqa: E402
import students          # noqa: E402
import telegram_api      # noqa: E402
from timetable import Timetable, period_times  # noqa: E402

with open(os.path.join(ROOT, "sample_data", "timetable_sample.json"), encoding="utf-8") as f:
    SAMPLE = Timetable._clean_all(json.load(f))

TUESDAY = datetime(2026, 10, 6, tzinfo=config.IST).date()   # a Tuesday


def at(hhmm, date=TUESDAY):
    hour, minute = map(int, hhmm.split(":"))
    return datetime(date.year, date.month, date.day, hour, minute, tzinfo=config.IST)


class FakeTelegram:
    """Pretends to be Telegram: remembers every call instead of sending it."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, **params):
        self.calls.append((method, params))
        return {"message_id": len(self.calls)}

    def texts(self):
        return [p.get("text", "") for m, p in self.calls if m in ("sendMessage", "editMessageText")]

    def buttons(self):
        """callback_data of every inline button in the last message that had buttons."""
        for method, params in reversed(self.calls):
            keyboard = params.get("reply_markup", {}).get("inline_keyboard")
            if keyboard:
                return [b["callback_data"] for row in keyboard for b in row]
        return []


def message(text, chat_id=42):
    return {"update_id": 1, "message": {"message_id": 7, "chat": {"id": chat_id},
                                        "from": {"first_name": "Aman"}, "text": text}}


def tap(data, chat_id=42):
    return {"update_id": 2, "callback_query": {
        "id": "cb1", "data": data, "from": {"first_name": "Aman"},
        "message": {"message_id": 99, "chat": {"id": chat_id}}}}


class TimetableTests(unittest.TestCase):
    tt = Timetable(SAMPLE)

    def test_picker_lists(self):
        self.assertEqual(self.tt.schools(), ["SOBT", "SOE", "SOICT", "SOVSAS"])
        self.assertIn(("1088", "B.Tech (CS)"), self.tt.programs("SOICT"))
        self.assertEqual(self.tt.sections("1088"), [("1", "BCS-I-A"), ("1239", "BCS-I-B"), ("2495", "BCS-I-C")])
        self.assertEqual(self.tt.batches("1"), [1, 2])

    def test_search_is_forgiving(self):
        self.assertEqual(self.tt.search_sections("bcs i a")[0], ("1", "BCS-I-A"))
        self.assertEqual(self.tt.search_sections("x"), [])

    def test_two_hour_lab_becomes_one_class(self):
        labs = [c for c in self.tt.classes_on("1", 2, batch=1) if c["type"] == "Lab"]
        self.assertEqual(len(labs), 1)
        self.assertEqual((labs[0]["start"], labs[0]["end"], labs[0]["code"]), ("15:30", "17:30", "CSE183"))

    def test_batch_zero_shows_every_batch(self):
        labs = [c for c in self.tt.classes_on("1", 2, batch=0) if c["type"] == "Lab"]
        self.assertEqual(sorted(c["batch"] for c in labs), [1, 2])

    def test_next_class(self):
        running, date, upcoming = self.tt.next_classes("1", 0, at("10:00"))
        self.assertEqual(running[0]["code"], "ECE101")
        self.assertEqual((date, upcoming[0]["code"], upcoming[0]["start"]), (TUESDAY, "ES101", "10:30"))

    def test_period_times(self):
        self.assertEqual(period_times(2), ("09:30", "10:30"))
        self.assertEqual(period_times(12), ("19:30", "20:30"))   # not in table → website's rule


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tt = Timetable(SAMPLE)
        self.telegram = FakeTelegram()
        self._real_call = telegram_api.call
        telegram_api.call = self.telegram
        students.remove(42)

    def tearDown(self):
        telegram_api.call = self._real_call

    def test_full_signup_flow(self):
        replies.handle_update(message("/start"), self.tt)
        self.assertIn("s:SOICT", self.telegram.buttons())

        replies.handle_update(tap("s:SOICT"), self.tt)
        self.assertIn("p:1088", self.telegram.buttons())

        replies.handle_update(tap("p:1088"), self.tt)
        self.assertEqual(self.telegram.buttons(), ["c:1", "c:1239", "c:2495", "s:SOICT"])

        replies.handle_update(tap("c:1"), self.tt)
        self.assertEqual(students.get(42)["section"], "BCS-I-A")
        self.assertEqual(self.telegram.buttons(), ["b:1", "b:2", "b:0"])     # asks for the batch

        replies.handle_update(tap("b:1"), self.tt)
        self.assertEqual(students.get(42)["batch"], 1)
        self.assertIn("All set", self.telegram.texts()[-1])

    def test_typing_class_name(self):
        replies.handle_update(message("bcs-i-b"), self.tt)
        self.assertEqual(self.telegram.buttons(), ["c:1239"])

    def test_today_needs_a_class_first(self):
        replies.handle_update(message("📅 Today"), self.tt)
        self.assertIn("/start", self.telegram.texts()[-1])

    def test_stop_forgets_student(self):
        students.save(42, section_id="1", section="BCS-I-A", batch=0)
        replies.handle_update(message("/stop"), self.tt)
        self.assertIsNone(students.get(42))


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tt = Timetable(SAMPLE)
        self.telegram = FakeTelegram()
        self._real_call = telegram_api.call
        telegram_api.call = self.telegram
        for chat_id, _ in students.everyone():
            students.remove(chat_id)
        if os.path.exists(reminders.SENT_FILE):
            os.remove(reminders.SENT_FILE)
        students.save(42, name="Aman", section_id="1", section="BCS-I-A",
                      program="B.Tech (CS)", school="SOICT", batch=1)

    def tearDown(self):
        telegram_api.call = self._real_call

    def test_reminder_sent_once_before_class(self):
        reminders.tick(self.tt, at("15:20"))
        reminders.tick(self.tt, at("15:22"))                  # same class → no repeat
        texts = self.telegram.texts()
        self.assertEqual(len(texts), 1)
        self.assertIn("Class in 10 minutes", texts[0])
        self.assertIn("CSE183", texts[0])                     # batch 1's lab
        self.assertNotIn("ICT181", texts[0])                  # batch 2's lab is hidden

    def test_no_reminder_for_second_hour_of_lab(self):
        reminders.tick(self.tt, at("16:25"))
        self.assertEqual(self.telegram.texts(), [])

    def test_morning_summary(self):
        reminders.tick(self.tt, at("07:31"))
        reminders.tick(self.tt, at("07:40"))
        texts = self.telegram.texts()
        self.assertEqual(len(texts), 1)
        self.assertIn("Good morning, Aman", texts[0])


if __name__ == "__main__":
    unittest.main()
