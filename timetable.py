"""
THE TIMETABLE
=============
Downloads the timetable from mygbu.in and answers questions like
"which classes does BCS-I-A have on Tuesday?"

In the n8n workflow this is the "Fetch GBU timetable" node, plus the
helper functions at the top of the Code nodes.

What one row from the API looks like (trimmed):
    {"TT_Day": "2", "TT_Period": "3", "Batch_Id": "0", "ActivityTag": "Lecture",
     "SectionName": "BCS-I-A", "Section_Id": "1", "Subject_Code": "CSE101",
     "subject_name": "Problem Solving Using C", "TeacherName": "...",
     "RoomName": "IL-104 (CLT)          ", "school": "SOICT", ...}
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

import config

DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
             5: "Friday", 6: "Saturday", 7: "Sunday"}

CACHE_FILE = os.path.join(config.DATA_DIR, "timetable_cache.json")


# ── Small helpers ─────────────────────────────────────────────────────────

def period_times(period):
    """(start, end) of a period, e.g. 2 -> ("09:30", "10:30")."""
    if period in config.PERIODS:
        return config.PERIODS[period]
    # Not in the table? Use the website's rule: 1-hour periods from 08:30.
    start = 8 * 60 + 30 + (period - 1) * 60
    return f"{start // 60:02d}:{start % 60:02d}", f"{(start + 60) // 60:02d}:{(start + 60) % 60:02d}"


def at_time(date, hhmm):
    """Combine a date and "HH:MM" into an exact moment in Indian time."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    return datetime(date.year, date.month, date.day, hour, minute, tzinfo=config.IST)


def simplify(text):
    """'BCS-I A' and 'bcs i-a' both become 'bcsia', so searching is forgiving."""
    return "".join(ch for ch in text.lower() if ch.isalnum())


def clean_row(raw):
    """Turn one messy row from the API into a small, tidy dict."""
    def text(key):
        return str(raw.get(key) or "").strip()   # values can be null or padded with spaces

    return {
        "school": text("school"),
        "program_id": text("program_id"),
        "program": text("program_name"),
        "section_id": text("Section_Id"),
        "section": text("SectionName"),
        "day": int(raw["TT_Day"]),                # 1 = Monday ... 7 = Sunday
        "period": int(raw["TT_Period"]),          # see config.PERIODS
        "batch": int(raw.get("Batch_Id") or 0),   # 0 = whole class, 1/2/3 = lab batch
        "type": text("ActivityTag") or "Class",   # Lecture / Lab / Tutorial
        "code": text("Subject_Code"),
        "subject": text("subject_name") or text("Subject_Code") or "Class",
        "teacher": text("TeacherName"),
        "room": text("RoomName"),
    }


def download(source):
    """Get the raw list of classes from a URL (or from a local .json file)."""
    if source.startswith("http"):
        response = requests.get(source, timeout=60,
                                headers={"User-Agent": "GBU-Timetable-Bot (student workshop)"})
        response.raise_for_status()
        return response.json()
    with open(source, encoding="utf-8") as f:
        return json.load(f)


# ── The Timetable ─────────────────────────────────────────────────────────

class Timetable:
    def __init__(self, rows=None):
        self.rows = rows or []       # list of clean rows
        self.next_refresh = 0.0      # time.time() when we should download again

    # ---------- loading ----------

    def refresh(self):
        """Download a fresh copy. If every source fails, use the copy saved on disk."""
        for source in config.TIMETABLE_SOURCES:
            try:
                raw = download(source)
                rows = self._clean_all(raw)
                self.rows = rows
                self._save_cache(raw)
                self.next_refresh = time.time() + config.TIMETABLE_REFRESH_MINUTES * 60
                print(f"Timetable loaded from {source}: {len(rows)} class slots")
                return True
            except Exception as error:   # network down, site changed, bad JSON...
                print(f"Could not load timetable from {source}: {error}")

        if not self.rows:                 # nothing in memory either -> try the disk copy
            try:
                with open(CACHE_FILE, encoding="utf-8") as f:
                    self.rows = self._clean_all(json.load(f))
                print(f"Using saved copy of the timetable ({len(self.rows)} class slots)")
            except (OSError, ValueError):
                print("No timetable available yet.")
        self.next_refresh = time.time() + 5 * 60   # try again in 5 minutes
        return False

    def refresh_if_old(self):
        if time.time() >= self.next_refresh:
            self.refresh()

    @staticmethod
    def _clean_all(raw):
        if not isinstance(raw, list) or not raw:
            raise ValueError("expected a non-empty list of classes")
        rows = []
        for item in raw:
            try:
                rows.append(clean_row(item))
            except (KeyError, TypeError, ValueError):
                pass                      # skip the odd broken row instead of crashing
        if not rows:
            raise ValueError("no usable rows")
        return rows

    @staticmethod
    def _save_cache(raw):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(raw, f)

    # ---------- picking a class: school -> program -> section -> batch ----------

    def schools(self):
        return sorted({r["school"] for r in self.rows if r["school"]})

    def programs(self, school):
        """[(program_id, program_name), ...] for one school."""
        found = {r["program_id"]: r["program"] for r in self.rows if r["school"] == school}
        return sorted(found.items(), key=lambda item: item[1])

    def sections(self, program_id):
        """[(section_id, section_name), ...] for one program."""
        found = {r["section_id"]: r["section"] for r in self.rows if r["program_id"] == program_id}
        return sorted(found.items(), key=lambda item: item[1])

    def section_info(self, section_id):
        for r in self.rows:
            if r["section_id"] == section_id:
                return {key: r[key] for key in ("section_id", "section", "program_id", "program", "school")}
        return None

    def search_sections(self, text):
        """Find sections by (part of) their name. Exact matches come first."""
        wanted = simplify(text)
        if len(wanted) < 2:
            return []
        found = {r["section_id"]: r["section"] for r in self.rows if wanted in simplify(r["section"])}
        return sorted(found.items(), key=lambda item: (simplify(item[1]) != wanted, item[1]))

    def batches(self, section_id):
        """Lab batches that exist for a section, e.g. [1, 2]. Empty if labs aren't split."""
        return sorted({r["batch"] for r in self.rows if r["section_id"] == section_id and r["batch"] > 0})

    # ---------- the important one ----------

    def classes_on(self, section_id, day, batch=0):
        """
        All classes of one section on one day (1 = Monday), in time order.
        batch=0 means "show every batch". Back-to-back periods of the same
        subject (like a 2-hour lab) are joined into one class.
        """
        rows = [r for r in self.rows
                if r["section_id"] == section_id and r["day"] == day
                and (batch == 0 or r["batch"] in (0, batch))]
        rows.sort(key=lambda r: (r["period"], r["batch"], r["code"]))

        classes = []
        seen = set()
        for r in rows:
            what = (r["code"], r["subject"], r["type"], r["teacher"], r["room"], r["batch"])
            if (what, r["period"]) in seen:
                continue                  # the API sometimes repeats a row
            seen.add((what, r["period"]))

            previous = next((c for c in classes
                             if c["what"] == what and c["last_period"] == r["period"] - 1), None)
            if previous:                  # same class continues -> make it longer
                previous["last_period"] = r["period"]
                previous["end"] = period_times(r["period"])[1]
            else:
                start, end = period_times(r["period"])
                classes.append({
                    "what": what,
                    "first_period": r["period"], "last_period": r["period"],
                    "start": start, "end": end,
                    "subject": r["subject"], "code": r["code"], "type": r["type"],
                    "teacher": r["teacher"], "room": r["room"], "batch": r["batch"],
                })

        for c in classes:
            del c["what"]                 # only needed while joining periods
        classes.sort(key=lambda c: (c["start"], c["batch"]))
        return classes

    def next_classes(self, section_id, batch, now):
        """
        What's happening now and what's next.
        Returns (running_now, date_of_next, next_classes). Looks up to a week ahead.
        """
        running = []
        for days_ahead in range(8):
            date = (now + timedelta(days=days_ahead)).date()
            classes = self.classes_on(section_id, date.isoweekday(), batch)
            if days_ahead == 0:
                running = [c for c in classes
                           if at_time(date, c["start"]) <= now < at_time(date, c["end"])]
                classes = [c for c in classes if at_time(date, c["start"]) > now]
            if classes:
                first_start = classes[0]["start"]
                return running, date, [c for c in classes if c["start"] == first_start]
        return running, None, []
