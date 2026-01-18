# -*- coding: utf-8 -*-
import requests
import json

TOKEN = "8383493744:AAF-ujWtMO_BuxeRDrR2O8vmWAuE4jXFFsQ"
CHAT_ID = 1046746312

print("=== TEST BOT ===")

print("1. Bot info:")
me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe").json()
print(json.dumps(me, indent=2, ensure_ascii=False))

print("\n2. Delete webhook...")
delete = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook").json()
print(json.dumps(delete, indent=2, ensure_ascii=False))

print("\n3. Send test message...")
send = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": "TEST: Message sent via Python API",
        "parse_mode": "Markdown"
    }
).json()
print(json.dumps(send, indent=2, ensure_ascii=False))

print("\n4. Check incoming messages...")
updates = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-10").json()
print(f"Found messages: {len(updates.get('result', []))}")
for msg in updates.get('result', []):
    if 'message' in msg:
        print(f"  - {msg['message'].get('text', 'No text')}")

print("\n5. Restore webhook...")
set_wh = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook",
    json={"url": "https://tarot-bot-3yla.onrender.com/webhook"}
).json()
print(json.dumps(set_wh, indent=2, ensure_ascii=False))

print("\n=== TEST COMPLETE ===")
print("Check Telegram NOW!")
