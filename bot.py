from flask import Flask, request, jsonify
import os
import requests
import logging
import random

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
else:
    logger.info(f"✅ BOT_TOKEN установлен, длина: {len(BOT_TOKEN)}")

# Колода Таро
TAROT_CARDS = [
    {"name": "🃏 Шут", "meaning": "Начало нового пути, невинность, спонтанность"},
    {"name": "🧙 Маг", "meaning": "Сила воли, мастерство, ресурсы"},
    {"name": "👑 Императрица", "meaning": "Изобилие, природа, материнство"},
    {"name": "🏛️ Император", "meaning": "Структура, власть, контроль"},
    {"name": "🙏 Иерофант", "meaning": "Традиции, духовность, вера"},
    {"name": "💑 Влюбленные", "meaning": "Выбор, отношения, гармония"},
    {"name": "⛵ Колесница", "meaning": "Победа, контроль, движение"},
    {"name": "⚖️ Правосудие", "meaning": "Баланс, карма, справедливость"},
    {"name": "🧘 Отшельник", "meaning": "Самоанализ, уединение, мудрость"},
    {"name": "🎡 Колесо Фортуны", "meaning": "Судьба, циклы, удача"},
    {"name": "💪 Сила", "meaning": "Храбрость, сострадание, контроль"},
    {"name": "🙎‍♂️ Повешенный", "meaning": "Сдача, новая перспектива, жертва"},
    {"name": "💀 Смерть", "meaning": "Конец, трансформация, новое начало"},
    {"name": "😇 Умеренность", "meaning": "Баланс, терпение, гармония"},
    {"name": "👿 Дьявол", "meaning": "Искушение, зависимость, ограничения"},
    {"name": "⚡ Башня", "meaning": "Внезапные перемены, откровение, разрушение"},
    {"name": "⭐ Звезда", "meaning": "Надежда, вдохновение, духовность"},
    {"name": "🌙 Луна", "meaning": "Интуиция, подсознание, иллюзии"},
    {"name": "☀️ Солнце", "meaning": "Радость, успех, жизненная сила"},
    {"name": "🔄 Суд", "meaning": "Возрождение, призыв к действию"},
    {"name": "🌍 Мир", "meaning": "Завершение, целостность, достижение"},
]

def send_message(chat_id, text, parse_mode='Markdown'):
    """Отправляет сообщение через Telegram API"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        logger.info(f"📤 Отправляю сообщение в chat_id {chat_id}: {text[:50]}...")
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка отправки: {response.text}")
        else:
            logger.info(f"✅ Сообщение отправлено успешно")
        
        return response.json()
    except Exception as e:
        logger.error(f"🚨 Ошибка при отправке: {e}")
        return None

def generate_tarot_reading(question):
    """Генерирует расклад Таро"""
    cards = random.sample(TAROT_CARDS, 3)
    
    interpretation = f"""🔮 *Расклад Таро на вопрос:* "{question}"

*Карта 1 (Прошлое/Ситуация):* {cards[0]['name']}
{cards[0]['meaning']}

*Карта 2 (Настоящее/Вызов):* {cards[1]['name']}
{cards[1]['meaning']}

*Карта 3 (Будущее/Результат):* {cards[2]['name']}
{cards[2]['meaning']}

✨ *Совет:* Прислушайся к своей интуиции и доверься процессу.
💫 *Помни:* Таро показывает тенденции, но не предопределяет будущее."""
    
    return interpretation

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной webhook от Telegram"""
    try:
        data = request.get_json()
        logger.info(f"📥 Получен webhook от пользователя")
        
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        # Проверяем разные типы обновлений
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text'].strip()
            chat_id = data['message']['chat']['id']
            user_name = data['message']['from'].get('first_name', 'друг')
            
            logger.info(f"👤 {user_name} ({chat_id}): {message_text}")
            
            # Обработка команд
            if message_text.startswith('/start'):
                response_text = f"""🔮 *Привет, {user_name}!*

Я - бот-таролог *@Tarotyour_bot*!

✨ *Доступные команды:*
/start - это сообщение
/tarot - сделать расклад Таро
/help - помощь

💫 Напиши /tarot для расклада!

*Бот работает для всех пользователей!* 🎉"""
                
                result = send_message(chat_id, response_text)
                logger.info(f"✅ Отправлен ответ на /start")
                
            elif message_text.startswith('/tarot'):
                response_text = f"""🌀 *{user_name}, отлично!* 

Напиши свой вопрос для расклада Таро.

💭 *Примеры вопросов:*
• Что меня ждет в отношениях?
• Какой выбор сделать?
• Что важного произойдет в ближайшее время?"""
                send_message(chat_id, response_text)
                
            elif message_text.startswith('/help'):
                response_text = """🔮 *Помощь:*

• /start - начать общение
• /tarot - сделать расклад
• Просто напиши вопрос - и я сделаю расклад

📊 *Как это работает:*
1. Вы задаете вопрос
2. Я выбираю 3 карты Таро
3. Даю интерпретацию расклада

💖 Бот абсолютно бесплатный!"""
                send_message(chat_id, response_text)
                
            else:
                # Если это не команда, делаем расклад на произвольный вопрос
                if len(message_text) > 3:  # Игнорируем слишком короткие сообщения
                    reading = generate_tarot_reading(message_text)
                    send_message(chat_id, reading)
                else:
                    response_text = f"""✨ *{user_name}, задай вопрос подробнее!*

💭 Напиши что-то вроде:
• "Что ждет меня на работе?"
• "Как улучшить отношения?"
• "Стоит ли мне менять профессию?"

Или используй команду /tarot для подсказок!"""
                    send_message(chat_id, response_text)
            
            return jsonify({"status": "success", "processed": True}), 200
        
        return jsonify({"status": "success", "processed": False}), 200
        
    except Exception as e:
        logger.error(f"🚨 Ошибка в webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook"""
    try:
        if not BOT_TOKEN:
            return jsonify({"error": "BOT_TOKEN не установлен"}), 400
        
        # Получаем URL для webhook
        webhook_url = request.host_url.rstrip('/') + '/webhook'
        logger.info(f"🔗 Устанавливаю webhook на: {webhook_url}")
        
        # Устанавливаем через Telegram API
        telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.post(telegram_url, json={'url': webhook_url}, timeout=10)
        
        result = {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "webhook_url": webhook_url,
            "telegram_response": response.json() if response.status_code == 200 else response.text
        }
        
        logger.info(f"🌐 Webhook установлен: {result}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"🚨 Ошибка установки webhook: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/test_all', methods=['GET'])
def test_all():
    """Тестовая отправка сообщения ЛЮБОМУ пользователю"""
    try:
        if not BOT_TOKEN:
            return jsonify({"error": "BOT_TOKEN не установлен"}), 400
        
        # Получаем chat_id из параметра запроса
        chat_id = request.args.get('chat_id')
        
        if not chat_id:
            return jsonify({
                "error": "Не указан chat_id",
                "usage": "/test_all?chat_id=ВАШ_CHAT_ID",
                "note": "Чтобы получить свой chat_id, напишите боту @userinfobot в Telegram"
            }), 400
        
        test_message = f"""🔮 *Тестовое сообщение от бота!*

Бот работает для всех пользователей! 🎉

✨ *Проверка функций:*
✅ Webhook активен
✅ Бот отвечает на команды
✅ Расклад Таро работает

💫 *Попробуй команды:*
/start - приветствие
/tarot - расклад Таро
/help - помощь

*Бот готов к работе!* 💖"""
        
        result = send_message(int(chat_id), test_message)
        
        return jsonify({
            "success": True if result and result.get('ok') else False,
            "chat_id": chat_id,
            "message": "Тестовое сообщение отправлено",
            "telegram_response": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/bot_info', methods=['GET'])
def bot_info():
    """Информация о боте"""
    try:
        if not BOT_TOKEN:
            return jsonify({"error": "BOT_TOKEN не установлен"}), 400
        
        # Получаем информацию о боте
        telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(telegram_url, timeout=10)
        
        return jsonify({
            "bot_token_exists": bool(BOT_TOKEN),
            "bot_token_length": len(BOT_TOKEN) if BOT_TOKEN else 0,
            "bot_info": response.json() if response.status_code == 200 else None,
            "webhook_url": request.host_url.rstrip('/') + '/webhook',
            "status": "active",
            "description": "Бот-таролог для всех пользователей",
            "endpoints": {
                "set_webhook": "/set_webhook",
                "test_all": "/test_all?chat_id=YOUR_CHAT_ID",
                "health": "/health"
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья"""
    return jsonify({
        "status": "healthy",
        "service": "Tarot Bot",
        "bot": "@Tarotyour_bot",
        "description": "Универсальный бот-таролог для всех пользователей",
        "features": ["Таро-расклады", "Поддержка всех пользователей", "Работает 24/7"],
        "timestamp": "2026-01-18T21:00:00Z"
    })

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "message": "🔮 Tarot Bot API работает!",
        "bot": "@Tarotyour_bot",
        "description": "Универсальный бот-таролог для ВСЕХ пользователей Telegram",
        "instructions": [
            "1. Установите webhook: /set_webhook",
            "2. Добавьте бота @Tarotyour_bot в Telegram",
            "3. Напишите /start для начала"
        ],
        "note": "Бот больше не привязан к конкретному chat_id. Работает для всех!",
        "endpoints": {
            "set_webhook": "/set_webhook",
            "test": "/test_all?chat_id=YOUR_CHAT_ID",
            "bot_info": "/bot_info",
            "health": "/health"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Запуск универсального бота на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
