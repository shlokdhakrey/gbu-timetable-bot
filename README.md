# GBU Timetable Bot

A Telegram bot for Gautam Buddha University students. A student picks their class once, and after that the bot:

- sends them the day's timetable at 7:30 AM
- reminds them 10 minutes before each class, with the subject, room and teacher
- answers Today / Tomorrow / Next class / Week whenever they ask

It is built twice, because this started life as a beginner workshop: once as an n8n workflow, once as plain Python. Both versions give the same answers to the same messages, and they were tested against each other.

| | n8n workflow | Python |
|---|---|---|
| Where | [`n8n/gbu-timetable-bot.json`](n8n/) | this folder (`bot.py` plus six small modules) |
| Good for | watching the data move, box by box | seeing how it actually works |
| Needs | an n8n account or server | Python 3.9+ and one library (`requests`) |

![The n8n workflow](docs/n8n-canvas.png)

## What a student sees

| Student does | Bot replies |
|---|---|
| `/start` | buttons: School, then Program, then Class, then lab batch |
| types `BCS-I-A` | finds the class; one tap saves it |
| Today / Tomorrow | that day's classes with time, room and teacher |
| Next class | what is on right now and what comes next |
| Week | Mon to Sun buttons, each showing that day |
| `/stop` | forgets them, no more messages |
| nothing, at 7:30 AM | the morning summary: "Good morning! Here's your day..." |
| nothing, 10 minutes before a class | a reminder for the class about to start |

A reminder looks like this:

```
Class in 10 minutes!

15:30-17:30 - Lab
Problem Solving Using C Lab
CSE183 - Anurag Singh Baghel - IP107
```

Two-hour labs show up as one class, 15:30 to 17:30, with a single reminder. If a class splits its labs into batches, the student picks their batch and only sees their own lab.

## How it works

Two things can set the bot off: a student writing to it, or the clock ticking.

A message arrives:

1. fetch the timetable
2. work out what the message means
3. look up the student
4. do one of: show the class picker, save the chosen class, build a timetable reply, forget the student, show help
5. send the reply to Telegram

The clock, every 5 minutes:

1. is it 7:30, or is a class starting in 10 minutes? if not, stop here and do nothing
2. fetch the timetable
3. load every student
4. build a morning summary, or a reminder, for each of them
5. send to Telegram

That is the n8n canvas, described in words. The Python version does the same steps as functions; the table further down maps one to the other.

## Where the timetable comes from

Nobody gave us an API, so we went looking for one.

1. Open <https://mygbu.in/db> in Chrome, press F12, open the Network tab, filter on Fetch/XHR.
2. Reload the page. It pulls down a single JSON file holding every class in the university.
3. We saved that session as a `.har` file and read through it to work out what the fields mean.

| URL | Notes |
|---|---|
| `https://mygbu.in/schd/api.php` | live data, around 3 MB. It is what the Free rooms and Free teachers pages use, and it is what we use. |
| `https://samay.mygbu.in/api.php` | the mirror behind Browse timetables. Compressed, around 0.6 MB, but updated less often. We keep it as a fallback. |

No login is needed. Each item in the file is one class slot:

```json
{ "TT_Day": "2", "TT_Period": "8", "Batch_Id": "1", "ActivityTag": "Lab",
  "Section_Id": "1", "SectionName": "BCS-I-A", "program_name": "B.Tech (CS)", "school": "SOICT",
  "Subject_Code": "CSE183", "subject_name": "Problem Solving Using C Lab",
  "TeacherName": "Anurag Singh Baghel", "RoomName": "IP107          " }
```

| Field | Meaning |
|---|---|
| `TT_Day` | 1 is Monday, up to 6 for Saturday, 7 for Sunday |
| `TT_Period` | 1 to 11. The times live in a table in `config.py`, or in the Settings node: period 1 is 08:30-09:30, then an hour each, which is the rule the website's own JavaScript uses |
| `Batch_Id` | 0 for the whole class, 1 / 2 / 3 for a lab batch |
| `Section_Id` | a stable id for the class. The names have stray spaces in them, the ids do not |
| `school`, `program_name`, `SectionName` | the three levels of the class picker |

The messy parts the code has to absorb: names padded out with spaces, missing rooms and teachers, two-hour labs stored as two separate periods, duplicate rows, and a response that sometimes starts with blank space.

## Run the Python version

```bash
pip install -r requirements.txt          # Windows: py -m pip install -r requirements.txt

python try_it.py BCS-I-A                 # see it work in the terminal, no Telegram needed
python try_it.py BCS-I-A tuesday 1       # Tuesday, lab batch 1
```

To turn it into a real bot:

1. On Telegram, open @BotFather, send `/newbot`, copy the token it gives you.
2. Copy `.env.example` to `.env` (`cp .env.example .env`, or `copy .env.example .env` on Windows) and paste the token in.
3. Start it:

```bash
python bot.py
```

Send `/start` to your bot. Ctrl+C stops it. Students and sent reminders are kept in `data/`.

If you have no way to reach mygbu.in, put `TIMETABLE_URL=sample_data/timetable_sample.json` in `.env`. That file has every first-year B.Tech class in it, taken on 30 Sep 2026.

Tests: `python -m unittest discover tests -v`. They need neither internet nor a token.

## Run the n8n version

The short version: import `n8n/gbu-timetable-bot.json`, create the Telegram credential, paste the token into the Settings node, run "Create students table" once, then publish. The full steps, and the things that catch people out, are in [n8n/README.md](n8n/README.md).

## The same thing in both versions

Node names on the canvas start with a small icon; only the text is given here.

| n8n node | Python |
|---|---|
| Student sends a message | `telegram_api.get_updates()`, in the loop in `bot.py` |
| Every 5 minutes | `reminders.tick()`, called by `bot.py` every few seconds |
| Settings | `config.py` |
| Fetch GBU timetable | `timetable.Timetable.refresh()` |
| Understand message | `replies.understand()` |
| Find / Save / Forget student | `students.get()` / `save()` / `remove()` |
| What do they want? | the `ACTIONS` table in `replies.py` |
| Show class picker | `replies.show_schools()`, `show_programs()`, `show_sections()`, `search()` |
| Prepare row, Save, Confirm | `replies.save_class()`, `save_batch()`, `finish_setup()` |
| Build timetable reply | `replies.show_day()`, `show_next()`, `show_week()`, plus `messages.py` |
| Anything due now? | the time checks in `reminders.tick()` |
| Build summary / reminders | `reminders.send_morning_summaries()`, `send_class_reminders()` |
| Send to Telegram | `telegram_api.call()` |

Three things the Python version does that the workflow does not:

- it caches the timetable for 3 hours, rather than downloading 3 MB for every message
- if mygbu.in is down it falls back to the mirror, and then to the last copy it saved
- it stops messaging students who have blocked the bot

## Files

```
bot.py            start here: the main loop (poll Telegram, reply, watch the clock)
config.py         settings: period timings, reminder time, where the data comes from
timetable.py      download and make sense of the mygbu.in data (join 2-hour labs, next class)
students.py       remember each student's class in data/students.json
replies.py        the brain: what to do with each message or button tap
messages.py       every text and button the bot sends
reminders.py      the clock: 7:30 summary and reminders, never sends twice
telegram_api.py   the four Telegram API calls we need, over plain HTTP
try_it.py         poke at the timetable logic from your terminal
tests/            unit tests, offline
sample_data/      first-year B.Tech timetable snapshot, for working offline
n8n/              the n8n workflow and how to import it
```

## Running it as a workshop, roughly 90 minutes

1. Demo, 10 minutes. Everyone messages the bot, picks their class, taps Today.
2. Where does the data come from, 15 minutes. Open mygbu.in, then DevTools, Network, `api.php`. Read one JSON row together.
3. n8n walkthrough, 25 minutes. Follow the numbered notes on the canvas. Open Executions, click through a real run, and watch a message turn into an action and then into a reply. Open Data tables, then gbu_students.
4. The same thing in Python, 25 minutes. Run `try_it.py`. Use the table above to find each n8n node in the code. Run `bot.py`.
5. Exercises, 15 minutes. Pick one from below.

### Exercises

1. Easy: send reminders 15 minutes before class instead of 10.
2. Easy: change the free-period line, or add a lunch message.
3. Medium: add `/free`, listing today's free periods.
4. Medium: add `/room IL-104`, showing who is in that room right now, like the website's Free rooms page.
5. Medium: send a 9 PM preview of tomorrow's classes.
6. Harder, in n8n: drop students who have blocked the bot. Hint: look at the Send node's output for error 403.
7. Harder, in n8n: stop downloading 3 MB per message. Cache the timetable the way the Python version does.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python bot.py` says it found no bot token | create `.env` from `.env.example` and paste the token in |
| Telegram didn't accept the token | copy it again from @BotFather: no spaces, no quotes |
| The Python bot and n8n fight over messages | one bot can only deliver to one place. Make a second bot in @BotFather |
| `Conflict: terminated by other getUpdates request` | `bot.py` is running twice. Close the other terminal |
| The n8n bot doesn't reply | see [n8n/README.md](n8n/README.md#troubleshooting) |
| mygbu.in is slow or down | Python falls back to the mirror or its saved copy, or set `TIMETABLE_URL=sample_data/timetable_sample.json` |
| Odd characters in the Windows terminal | use Windows Terminal, or run `chcp 65001` first |

## Notes for whoever runs the session

- Check the period timings against the real bell schedule. They follow the mygbu.in website's rule: 08:30 start, an hour each. Change them in `config.py` under `PERIODS`, and in the Settings node under `periods`.
- Server load: every chat message in n8n downloads `schd/api.php`, about 3 MB and uncompressed. Turning on gzip for that URL would make it four or five times smaller; the samay mirror already uses Brotli.
- Use two bots, one for the n8n demo and one for the Python demo.
- The data is public, the website loads it without a login, but be kind to the server. The Python version fetches it once every 3 hours at most.
