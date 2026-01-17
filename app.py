from flask import Flask, request, jsonify
import os
import requests
import logging
import random
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# Простая база данных в памяти (временно)
users_db = {}
readings_db = {}

# Карты Таро для разных раскладов
TAROT_DECK = {
    "Маг": {"meaning": "Воля, мастерство, начало нового дела", "reverse": "Манипуляции, слабость воли"},
    "Верховная Жрица": {"meaning": "Интуиция, тайны, внутренний голос", "reverse": "Игнорирование интуиции, поверхностность"},
    "Императрица": {"meaning": "Изобилие, творчество, материнство", "reverse": "Зависимость, творческий блок"},
    "Император": {"meaning": "Структура, власть, стабильность", "reverse": "Тирания, жесткость"},
    "Иерофант": {"meaning": "Традиции, духовность, мудрость", "reverse": "Догматизм, лицемерие"},
    "Влюбленные": {"meaning": "Выбор, гармония, отношения", "reverse": "Конфликт, неверный выбор"},
    "Колесница": {"meaning": "Движение, победа, контроль", "reverse": "Застой, потеря контроля"},
    "Сила": {"meaning": "Смелость, страсть, внутренняя сила", "reverse": "Слабость, страх"},
    "Отшельник": {"meaning": "Самоанализ, мудрость, одиночество", "reverse": "Изоляция, страх одиночества"},
    "Колесо Фортуны": {"meaning": "Судьба, перемены, циклы", "reverse": "Сопротивление переменам, неудача"},
    "Справедливость": {"meaning": "Баланс, карма, правда", "reverse": "Несправедливость, безответственность"},
    "Повешенный": {"meaning": "Жертва, новый взгляд, пауза", "reverse": "Бесполезная жертва, застой"},
    "Смерть": {"meaning": "Трансформация, конец, обновление", "reverse": "Сопротивление изменениям, страх"},
    "Умеренность": {"meaning": "Баланс, гармония, терпение", "reverse": "Дисбаланс, нетерпение"},
    "Дьявол": {"meaning": "Искушение, зависимость, материальность", "reverse": "Освобождение, преодоление"},
    "Башня": {"meaning": "Внезапные изменения, разрушение", "reverse": "Боязнь перемен, отсрочка"},
    "Звезда": {"meaning": "Надежда, вдохновение, исцеление", "reverse": "Разочарование, потеря веры"},
    "Луна": {"meaning": "Интуиция, иллюзии, подсознание", "reverse": "Ясность, разоблачение"},
    "Солнце": {"meaning": "Радость, успех, ясность", "reverse": "Временные трудности, эго"},
    "Суд": {"meaning": "Обновление, призыв, прощение", "reverse": "Сожаление, сопротивление"},
    "Мир": {"meaning": "Завершение, успех, путешествие", "reverse": "Незавершенность, застой"},
    "Шут": {"meaning": "Начало, невинность, риск", "reverse": "Безрассудство, застой"}
}

class SimpleTarotBot:
    def __init__(self):
        self.personality = """Ты - мудрый таролог и духовный наставник по имени Ариэль. Помогаешь людям через карты Таро."""
    
    def draw_card(self):
        """Вытаскивание одной карты"""
        card_name = random.choice(list(TAROT_DECK.keys()))
        is_reversed = random.random() < 0.3
        meaning = TAROT_DECK[card_name]["reverse"] if is_reversed else TAROT_DECK[card_name]["meaning"]
        
        return {
            "name": card_name,
            "meaning": meaning,
            "reversed": is_reversed
        }
    
    def get_interpretation(self, question, card):
        """Получение интерпретации от DeepSeek"""
        try:
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            system_prompt = f"""Ты - опытный таролог. Интерпретируй карту Таро.

Карта: {card['name']} ({'перевернута' if card['reversed'] else 'прямая'})
Значение: {card['meaning']}

Вопрос: {question}

Дай мудрую и поддерживающую интерпретацию."""
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Интерпретируй эту карту, пожалуйста."}
                ],
                "temperature": 0.8,
                "max_tokens": 300
            }
            
            response = requests.post('https://api.deepseek.com/v1/chat/completions', 
                                   headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
            
            return "Карта говорит о необходимости доверять своей интуиции."
                
        except Exception as e:
            logger.error(f"Error getting interpretation: {e}")
            return "Мудрость карт приходит через тишину."
    
    def get_response(self, user_message):
        """Получение ответа от DeepSeek для обычного общения"""
        try:
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            messages = [
                {"role": "system", "content": self.personality},
                {"role": "user", "content": user_message}
            ]
            
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 200
            }
            
            response = requests.post('https://api.deepseek.com/v1/chat/completions', 
                                   headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
            
            return "🌀 Энергия сегодня рассеяна. Попробуй позже."
                
        except Exception as e:
            logger.error(f"Error calling DeepSeek: {e}")
            return "🌀 Произошла ошибка."

# Инициализация бота
tarot_bot = SimpleTarotBot()

# Webhook endpoint для Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        try:
            data = request.get_json()
            logger.info(f"Received webhook: {data}")
            
            # Проверяем что это сообщение
            if 'message' in data and 'text' in data['message']:
                message_text = data['message']['text']
                chat_id = data['message']['chat']['id']
                
                # Обработка команд
                if message_text == '/start':
                    response_text = """🔮 *Добро пожаловать в Храм Мудрости Таро!*

Я - Ариэль, твой проводник в мир карт Таро.

✨ *Доступные команды:*
/tarot - Сделать расклад Таро
/help - Помощь

💫 Напиши свой вопрос, и я помогу тебе!"""
                    
                    # Отправляем ответ (в реальном боте здесь будет вызов Telegram API)
                    logger.info(f"Would send to chat {chat_id}: {response_text}")
                    
                elif message_text == '/tarot':
                    response_text = "🌀 Напиши свой вопрос для расклада Таро:"
                    logger.info(f"Would send to chat {chat_id}: {response_text}")
                    
                else:
                    # Проверяем, ожидается ли вопрос для расклада
                    if chat_id in users_db and users_db[chat_id].get('awaiting_question'):
                        # Делаем расклад
                        card = tarot_bot.draw_card()
                        interpretation = tarot_bot.get_interpretation(message_text, card)
                        
                        response_text = f"""✨ *Карта выпала!*

*Вопрос:* {message_text}
*Карта:* {card['name']} {'🔄 (перевернута)' if card['reversed'] else ''}
*Значение:* {card['meaning']}

🔍 *Интерпретация:*
{interpretation}"""
                        
                        # Сохраняем расклад
                        readings_db[chat_id] = {
                            'question': message_text,
                            'card': card,
                            'interpretation': interpretation,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Сбрасываем флаг ожидания вопроса
                        users_db[chat_id]['awaiting_question'] = False
                        
                    else:
                        # Обычный разговор
                        response_text = tarot_bot.get_response(message_text)
                        # Устанавливаем флаг ожидания вопроса если пользователь хочет расклад
                        if 'таро' in message_text.lower() or 'расклад' in message_text.lower():
                            users_db[chat_id] = {'awaiting_question': True}
                    
                    logger.info(f"Would send to chat {chat_id}: {response_text}")
                
                return jsonify({"status": "success", "message": "Processed"}), 200
            
            return jsonify({"status": "success", "message": "No text message"}), 200
            
        except Exception as e:
            logger.error(f"Error in webhook: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400

# Установка webhook
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook"""
    try:
        if not BOT_TOKEN:
            return jsonify({"error": "BOT_TOKEN not configured"}), 400
        
        # URL для webhook
        webhook_url = request.args.get('url', request.host_url + 'webhook')
        
        # В реальном приложении здесь будет вызов Telegram API
        # Для примера просто логируем
        logger.info(f"Webhook would be set to: {webhook_url}")
        
        return jsonify({
            "success": True,
            "webhook_url": webhook_url,
            "message": "В реальном боте здесь будет вызов Telegram API setWebhook"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# Проверка здоровья
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "bot": "Tarot Master 🔮",
        "version": "1.0",
        "timestamp": datetime.now().isoformat()
    })

# Главная страница
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "Tarot Bot API",
        "endpoints": {
            "home": "/",
            "health": "/health",
            "set_webhook": "/set_webhook",
            "webhook": "/webhook (POST only)"
        },
        "instructions": "1. Set BOT_TOKEN environment variable\n2. Visit /set_webhook to set webhook\n3. Bot will receive messages at /webhook"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
