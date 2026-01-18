from flask import Flask, request, jsonify
import os
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
else:
    logger.info(f"✅ BOT_TOKEN установлен, длина: {len(BOT_TOKEN)}")

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
        logger.info(f"📨 Ответ от Telegram: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка отправки: {response.text}")
        
        return response.json()
    except Exception as e:
        logger.error(f"🚨 Ошибка при отправке: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной webhook от Telegram"""
    try:
        data = request.get_json()
        logger.info(f"📥 Получен webhook: {data}")
        
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text']
            chat_id = data['message']['chat']['id']
            user_name = data['message']['from'].get('first_name', 'друг')
            
            logger.info(f"👤 Пользователь {user_name} ({chat_id}): {message_text}")
            
            # Обработка команд
            if message_text == '/start':
                response_text = f"""🔮 *Привет, {user_name}!*

Я - бот-таролог *@Tarotyour_bot*!

✨ *Доступные команды:*
/start - это сообщение
/tarot - сделать расклад Таро
/help - помощь

💫 Напиши /tarot для расклада!"""
                
                result = send_message(chat_id, response_text)
                logger.info(f"✅ Отправлен ответ на /start: {result}")
                
            elif message_text == '/tarot':
                response_text = "🌀 *Отлично! Напиши свой вопрос для расклада Таро:*"
                send_message(chat_id, response_text)
                
            elif message_text == '/help':
                response_text = """🔮 *Помощь:*

• /start - начать общение
• /tarot - сделать расклад
• Просто напиши вопрос

Бот работает на Render + Telegram API!"""
                send_message(chat_id, response_text)
                
            else:
                # Ответ на любое сообщение
                response_text = f"""✨ *{user_name}, ты написал(а):* "{message_text}"

💭 *Попробуй команды:*
/tarot - для расклада Таро
/help - для помощи"""
                
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

@app.route('/test_send', methods=['GET'])
def test_send():
    """Тестовая отправка сообщения (ваш chat_id из логов)"""
    try:
        if not BOT_TOKEN:
            return jsonify({"error": "BOT_TOKEN не установлен"}), 400
        
        # Ваш chat_id из логов: 1046746312
        test_chat_id = 1046746312
        test_message = "🔮 *Тестовое сообщение от бота!*\n\nЕсли ты это видишь, значит бот работает!"
        
        result = send_message(test_chat_id, test_message)
        
        return jsonify({
            "success": True,
            "chat_id": test_chat_id,
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
            "webhook_url": request.host_url.rstrip('/') + '/webhook'
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
        "timestamp": "2026-01-17T21:00:00Z",
        "endpoints": {
            "home": "/",
            "health": "/health",
            "bot_info": "/bot_info",
            "set_webhook": "/set_webhook",
            "test_send": "/test_send",
            "webhook": "/webhook (POST)"
        }
    })

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "message": "🔮 Tarot Bot API работает!",
        "bot": "@Tarotyour_bot",
        "instructions": "1. Установите webhook: /set_webhook\n2. Протестируйте отправку: /test_send\n3. Проверьте бота: /bot_info",
        "note": "Убедитесь что BOT_TOKEN установлен в Environment Variables на Render"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Запуск сервера на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
