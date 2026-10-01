"""
TALKING TO TELEGRAM
===================
A Telegram bot is just a program that sends HTTP requests to

    https://api.telegram.org/bot<YOUR_TOKEN>/<methodName>

That's all this file does. The methods we use:
    getUpdates           "any new messages for me?"
    sendMessage          send a message (optionally with buttons)
    editMessageText      change a message we already sent
    answerCallbackQuery  tell Telegram we handled a button tap

In the n8n workflow, the Telegram trigger and "Send to Telegram" do this job.
All methods: https://core.telegram.org/bots/api
"""

import requests

import config


class TelegramError(Exception):
    def __init__(self, method, code, description):
        super().__init__(f"{method} failed ({code}): {description}")
        self.code = code
        self.description = description or ""


def call(method, **params):
    """Call any Telegram Bot API method and return its result."""
    url = f"{config.TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/{method}"
    wait = params.get("timeout", 0) + 15          # getUpdates may wait `timeout` seconds
    response = requests.post(url, json=params, timeout=wait)
    try:
        data = response.json()
    except ValueError:
        raise TelegramError(method, response.status_code, response.text[:200])
    if not data.get("ok"):
        raise TelegramError(method, data.get("error_code"), data.get("description"))
    return data["result"]


# ── Buttons ───────────────────────────────────────────────────────────────

def inline_buttons(rows):
    """
    Buttons attached to a message. We write them as simple lists:
        [[("Batch 1", "b:1"), ("Batch 2", "b:2")], [("Back", "home")]]
    The second value (callback data) is what the bot receives when a button is tapped.
    """
    return {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row]
                                for row in rows]}


def menu_keyboard(rows):
    """Big buttons that replace the phone keyboard. Tapping one sends its text as a message."""
    return {"keyboard": [[{"text": label} for label in row] for row in rows],
            "resize_keyboard": True, "is_persistent": True}


# ── The calls we use ──────────────────────────────────────────────────────

def get_updates(offset=None, timeout=20):
    """Wait up to `timeout` seconds for new messages / button taps."""
    params = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        params["offset"] = offset
    return call("getUpdates", **params)


def send_message(chat_id, text, buttons=None, menu=None, remove_menu=False):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if buttons:
        params["reply_markup"] = inline_buttons(buttons)
    elif menu:
        params["reply_markup"] = menu_keyboard(menu)
    elif remove_menu:
        params["reply_markup"] = {"remove_keyboard": True}
    return call("sendMessage", **params)


def edit_message(chat_id, message_id, text, buttons=None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if buttons:
        params["reply_markup"] = inline_buttons(buttons)
    try:
        return call("editMessageText", **params)
    except TelegramError as error:
        if "message is not modified" in error.description:
            return None                  # student tapped the same button twice: nothing to do
        raise


def answer_callback(callback_id, text=None):
    params = {"callback_query_id": callback_id}
    if text:
        params["text"] = text
    try:
        call("answerCallbackQuery", **params)
    except TelegramError:
        pass                             # button tap too old to answer: harmless
