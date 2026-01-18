import requests
import json

TOKEN = "8383493744:AAF-ujWtMO_BuxeRDrR2O8vmWAuE4jXFFsQ"
CHAT_ID = 1046746312

print("🔍 Проверяем бота...")
me = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe").json()
print(f"Информация о боте: {me}")

print("\n🧹 Удаляем webhook...")
delete = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook").json()
print(f"Удаление: {delete}")

print("\n📨 Проверяем сообщения...")
updates = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json()
print(f"Сообщений в истории: {len(updates.get('result', []))}")
for msg in updates.get('result', []):
    print(f"  - {msg.get('message', {}).get('text', 'Нет текста')}")

print(f"\n📤 Отправляем тестовое сообщение в chat_id {CHAT_ID}...")
send = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": "🎯 ТЕСТ ИЗ PYTHON СКРИПТА\n\nЕсли видишь это - бот работает!",
        "parse_mode": "Markdown"
    }
).json()
print(f"Отправка: {send}")

print("\n🔄 Проверяем обновления после отправки...")
updates2 = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json()
print(f"Теперь сообщений: {len(updates2.get('result', []))}")

print("\n🌐 Восстанавливаем webhook...")
set_wh = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook",
    json={"url": "https://tarot-bot-3yla.onrender.com/webhook"}
).json()
print(f"Webhook восстановлен: {set_wh}")

print("\n✅ Тест завершен!")
