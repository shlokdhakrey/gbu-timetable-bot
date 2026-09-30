"""
💾  REMEMBERING STUDENTS
========================
Which student picked which class. Saved in data/students.json so the bot
remembers everyone even after a restart.

In the n8n workflow this is the  "gbu_students"  Data Table.

The file looks like this:
{
  "123456789": {"name": "Aman", "section_id": "1", "section": "BCS-I-A",
                "program": "B.Tech (CS)", "batch": 1}
}
(The key is the Telegram chat id.)
"""

import json
import os

import config

FILE = os.path.join(config.DATA_DIR, "students.json")


def _read():
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(data):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    temp = FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp, FILE)   # swap in one step, so a crash can't leave half a file


def get(chat_id):
    """The saved info for one student, or None if they haven't picked a class."""
    return _read().get(str(chat_id))


def save(chat_id, **fields):
    """Create or update a student, e.g. save(123, section="BCS-I-A", batch=1)."""
    data = _read()
    student = data.get(str(chat_id), {})
    student.update(fields)
    data[str(chat_id)] = student
    _write(data)
    return student


def remove(chat_id):
    data = _read()
    if data.pop(str(chat_id), None) is not None:
        _write(data)


def everyone():
    """[(chat_id, student), ...] for all students who picked a class."""
    return [(chat_id, s) for chat_id, s in _read().items() if s.get("section_id")]
