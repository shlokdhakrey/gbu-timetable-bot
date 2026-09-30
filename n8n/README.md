# The n8n version

`gbu-timetable-bot.json` is the whole bot as one n8n workflow: 23 nodes, with notes on the canvas that explain each part.

![The workflow](../docs/n8n-canvas.png)

## You need

- **n8n 2.x.** It uses *Data tables*, n8n's built-in storage, so there's no database to set up.
  - Easiest: **n8n Cloud** (the free trial is enough).
  - Self-hosted: Docker, or `npx n8n` (needs Node.js 24+).
- **n8n reachable over HTTPS from the internet.** Telegram *pushes* each message to n8n (a "webhook"), so `localhost` alone won't work. On a laptop, use a tunnel:

  ```bash
  cloudflared tunnel --url http://localhost:5678        # prints https://something.trycloudflare.com

  docker run -it --rm -p 5678:5678 \
    -e WEBHOOK_URL=https://something.trycloudflare.com/ \
    -e GENERIC_TIMEZONE=Asia/Kolkata \
    -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
  ```

  (ngrok works too: `ngrok http 5678`.)
- **A bot token** from **@BotFather** on Telegram (`/newbot`). Use a different bot from the Python version's.

## Set it up (5 minutes)

1. **Import.** In n8n, create a new workflow → click **⋯** next to the workflow name → **Import → From file** → pick `gbu-timetable-bot.json`.
2. **Telegram credential.** Open **💬 Student sends a message** → *Credential to connect with* → **Create new** → paste the token → Save.
3. **Settings.** Open **⚙️ Settings** → paste the **same token** into `botToken`.
4. **Create the table.** Open **🗄️ Create students table** → **Execute step**. Do this once. It creates a data table called `gbu_students`, which you can see under *Overview → Data tables*.
5. **Save and Publish** (top right).
6. Send `/start` to your bot. 🎉

## What to show in the workshop

- **Executions** tab: open any run and click each node to see the data change: raw Telegram update → *action* → reply JSON.
- **Data tables → gbu_students**: a new row appears each time someone picks their class.
- **⏰ Every 5 minutes** runs all day. Most runs stop at **🕐 Anything due now?** without downloading anything. That's a good lesson: do the cheap check first.

## Changing things (all in ⚙️ Settings)

| Setting | Meaning |
|---|---|
| `periods` | one `"HH:MM-HH:MM"` per period, period 1 first. Default: 08:30–09:30, 09:30–10:30, … |
| `morningAt` | time of the daily summary (`07:30`) |
| `remindMinutesBefore` | how early the reminder comes (`10`) |
| `timezone` | `Asia/Kolkata`. Every time is calculated in this zone, whatever timezone n8n itself runs in |
| `timetableUrl` | `https://mygbu.in/schd/api.php` (backup: `https://samay.mygbu.in/api.php`) |
| `telegramApi` | leave it as it is (it only changes for testing) |

## Troubleshooting

| Problem | Check |
|---|---|
| Nothing happens when you message the bot | Is the workflow **published**? Is n8n reachable over **HTTPS** (tunnel running, `WEBHOOK_URL` set)? |
| Runs appear in *Executions* but no reply arrives | Open the run → **📤 Send to Telegram** output. A `401`/`404` means the token in ⚙️ Settings is wrong or still the placeholder |
| *Data table … not found* | Run **🗄️ Create students table** once (step 4) |
| It worked, then stopped after testing in the editor | Clicking *Execute* on the Telegram trigger moves the bot's webhook to the editor. Publish again |
| The Python bot and n8n fight over messages | One bot delivers to one place only. Use two bots |
| Reminders at the wrong time | Check `periods` in ⚙️ Settings. Times are always Indian time |

## How it was tested

The workflow was imported into n8n 2.41 and published. Telegram was replaced with a local fake Telegram server, and 25 end-to-end checks were run against it: every chat path, button, data-table save/delete, the morning summary, reminders, and "nothing due". The checks were also run on an n8n set to the **US timezone** with the workflow's timezone setting removed, which is what an import gives you. They all passed.
