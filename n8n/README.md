# The n8n version

`gbu-timetable-bot.json` is the whole bot as one n8n workflow: 23 nodes, with notes on the canvas explaining each part. Node names on the canvas start with a small icon; only the text is given below.

![The workflow](../docs/n8n-canvas.png)

## What you need

- n8n 2.x. The workflow uses Data tables, n8n's built-in storage, so there is no database to set up.
  - Easiest: n8n Cloud. The free trial is enough.
  - Self-hosted: Docker, or `npx n8n` with Node.js 24+.
- n8n reachable over HTTPS from the internet. Telegram pushes each message to n8n through a webhook, so plain `localhost` will not do. On a laptop, use a tunnel:

  ```bash
  cloudflared tunnel --url http://localhost:5678        # prints https://something.trycloudflare.com

  docker run -it --rm -p 5678:5678 \
    -e WEBHOOK_URL=https://something.trycloudflare.com/ \
    -e GENERIC_TIMEZONE=Asia/Kolkata \
    -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
  ```

  ngrok works just as well: `ngrok http 5678`.
- A bot token from @BotFather on Telegram (`/newbot`). Use a different bot from the Python version's, since one bot can only deliver to one place.

## Set it up, about 5 minutes

1. Import. In n8n, create a new workflow, click the three dots next to the workflow name, then Import, then From file, and pick `gbu-timetable-bot.json`.
2. Telegram credential. Open the "Student sends a message" node, go to "Credential to connect with", choose Create new, paste the token, save.
3. Settings. Open the Settings node and paste the same token into `botToken`.
4. Create the table. Open "Create students table" and click Execute step. Once is enough. It creates a data table called `gbu_students`, which you can find under Overview, then Data tables.
5. Save and publish, top right.
6. Send `/start` to your bot.

## What to show in the workshop

- The Executions tab. Open any run and click through the nodes to watch the data change: raw Telegram update, then an action, then reply JSON.
- Data tables, then gbu_students. A new row appears every time someone picks their class.
- The "Every 5 minutes" trigger runs all day, but most runs stop at "Anything due now?" without downloading anything. That is worth pointing out: do the cheap check first.

## Changing things, all in the Settings node

| Setting | Meaning |
|---|---|
| `periods` | one `"HH:MM-HH:MM"` per period, period 1 first. Default: 08:30-09:30, 09:30-10:30, and so on |
| `morningAt` | when the daily summary goes out (`07:30`) |
| `remindMinutesBefore` | how early the reminder comes (`10`) |
| `timezone` | `Asia/Kolkata`. Every time is worked out in this zone, whatever timezone n8n itself runs in |
| `timetableUrl` | `https://mygbu.in/schd/api.php`, with `https://samay.mygbu.in/api.php` as the backup |
| `telegramApi` | leave it alone, it only changes for testing |

## Troubleshooting

| Problem | Check |
|---|---|
| Nothing happens when you message the bot | Is the workflow published? Is n8n reachable over HTTPS, with the tunnel running and `WEBHOOK_URL` set? |
| Runs show up in Executions but no reply arrives | Open the run and look at the "Send to Telegram" output. A 401 or 404 means the token in Settings is wrong, or still the placeholder |
| "Data table not found" | Run "Create students table" once, step 4 above |
| It worked, then stopped after you tested in the editor | Clicking Execute on the Telegram trigger moves the bot's webhook to the editor. Publish again |
| The Python bot and n8n fight over messages | One bot delivers to one place only. Use two bots |
| Reminders arrive at the wrong time | Check `periods` in Settings. Times are always Indian time |

## How it was tested

The workflow was imported into n8n 2.41 and published. Telegram was swapped for a local fake Telegram server, and 25 end-to-end checks were run against it: every chat path, every button, data table saves and deletes, the morning summary, reminders, and the "nothing due" case. The checks were run again on an n8n set to a US timezone with the workflow's timezone setting removed, which is what you get from a plain import. They all passed.
