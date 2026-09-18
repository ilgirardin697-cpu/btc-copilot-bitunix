#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper to obtain TELEGRAM_CHAT_ID without exposing your token in a browser URL.
"""

import getpass
import requests

print("=" * 68)
print("BTC COPILOT — TELEGRAM SETUP")
print("=" * 68)
print("1) In Telegram, open the bot you created with @BotFather.")
print("2) Press START or send: /start")
print("3) Come back here.")
print()

token = getpass.getpass("Paste your Telegram bot token (it will not be displayed): ").strip()
if not token:
    raise SystemExit("No token.")

url = f"https://api.telegram.org/bot{token}/getUpdates"
r = requests.get(url, params={"offset": -20, "limit": 20, "timeout": 0}, timeout=15)
r.raise_for_status()
payload = r.json()

if not payload.get("ok"):
    raise SystemExit(f"Telegram error: {payload}")

updates = payload.get("result") or []
candidates = []
for u in updates:
    msg = u.get("message") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    txt = msg.get("text", "")
    if cid is not None:
        candidates.append((cid, chat.get("first_name") or chat.get("username") or "chat", txt))

if not candidates:
    print("\nNo message found.")
    print("Send /start to your bot in Telegram and run this file again.")
    raise SystemExit(1)

cid, name, txt = candidates[-1]
print("\nSUCCESS")
print("Your TELEGRAM_CHAT_ID is:")
print()
print(cid)
print()
print("Copy ONLY that number. Do not upload your token to GitHub.")
