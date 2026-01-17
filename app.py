from flask import Flask, request, jsonify
import os
import requests
import logging
import random
import time
import threading
from datetime import datetime, timedelta
from payment import YookassaPayment
from database import db_manager, Base, engine, UserSubscription, SessionLocal

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID', 'test_shop_id')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY', 'test_secret_key')

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

MINOR_ARCANA = {
    "Туз Кубков": {"meaning": "Новые чувства, эмоциональное начало", "reverse": "Эмоциональные блоки"},
    "Двойка Кубков": {"meaning": "Взаимность, партнерство, гармония", "reverse": "Разрыв, дисгармония"},
    "Тройка Кубков": {"meaning": "Праздник, дружба, радость", "reverse": "Одиночество, излишества"},
    "Четверка Кубков": {"meaning": "Апатия, самоанализ", "reverse": "Новые возможности"},
    "Туз Мечей": {"meaning": "Прорыв, ясность, правда", "reverse": "Конфликт, жестокость"},
    "Двойка Мечей": {"meaning": "Тупик, выбор, равновесие", "reverse": "Неверный выбор"},
    "Рыцарь Мечей": {"meaning": "Действие, скорость, конфронтация", "reverse": "Импульсивность, агрессия"},
    "Королева Пентаклей": {"meaning": "Изобилие, практичность, забота", "reverse": "Материализм, жадность"},
    "Король Жезлов": {"meaning": "Лидерство, энергия, вдохновение", "reverse": "Тирания, упрямство"}
}

# Расклады Таро
SPREADS = {
    "past_present_future": {
        "name": "Прошлое-Настоящее-Будущее",
        "cards": 3,
        "positions": ["Прошлое", "Настоящее", "Будущее"],
        "description": "Классический расклад для понимания временных линий"
    },
    "relationship": {
        "name": "Отношения",
        "cards": 5,
        "positions": ["Ваши чувства", "Чувства партнера", "Динамика отношений", 
                     "Препятствия", "Потенциал развития"],
        "description": "Расклад для понимания любовных отношений"
    },
    "career": {
        "name": "Карьера",
        "cards": 4,
        "positions": ["Текущая ситуация", "Препятствия", "Скрытые возможности", "Рекомендации"],
        "description": "Анализ профессионального пути"
    },
    "yes_no": {
        "name": "Да/Нет",
        "cards": 1,
        "positions": ["Ответ"],
        "description": "Быстрый ответ на конкретный вопрос"
    }
}

# Инициализация бота будет после проверки токена
bot = None
application = None

class TarotMasterBot:
    def __init__(self):
        self.personality = """Ты - мудрый таролог и духовный наставник по имени Ариэль, 35 лет. 
        Обладаешь глубокими знаниями в области Таро, психологии и духовных практик.
        Твой стиль - мудрый, заботливый, немного мистический, но приземленный.
        Помогаешь людям видеть скрытые аспекты ситуаций через карты Таро."""
        
        self.active_spreads = {}
        self.user_questions = {}
    
    def send_welcome_message(self, chat_id):
        """Приветственное сообщение"""
        welcome_text = """🔮 *Добро пожаловать в Храм Мудрости Таро!*

Я - Ариэль, твой проводник в мир символов и инсайтов. 

✨ *Что я умею:*
• Проводить расклады Таро
• Помогать увидеть скрытые аспекты ситуаций
• Давать мудрые советы на основе карт
• Быть твоим духовным наставником

💫 *Готов(а) начать путешествие к себе?*"""
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [[InlineKeyboardButton("🌀 Начать сессию", callback_data="start_session")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def send_session_start(self, chat_id):
        """Начало сессии"""
        session_text = """🌀 *Настройка на энергию вопроса*

Перед раскладом важно сформулировать вопрос. 

*Примеры вопросов:*
• Что мне нужно знать о текущей ситуации?
• Какой путь выбрать?
• Что скрывает от меня эта ситуация?

📝 *Напиши свой вопрос:*"""
        
        bot.send_message(
            chat_id=chat_id,
            text=session_text,
            parse_mode='Markdown'
        )
    
    def draw_cards(self, count):
        """Вытаскивание карт"""
        all_cards = list(TAROT_DECK.items()) + list(MINOR_ARCANA.items())
        selected = random.sample(all_cards, min(count, len(all_cards)))
        
        cards = []
        for card_name, card_info in selected:
            is_reversed = random.random() < 0.3
            cards.append({
                "name": card_name,
                "meaning": card_info["reverse"] if is_reversed else card_info["meaning"],
                "reversed": is_reversed,
                "symbol": self.get_card_symbol(card_name)
            })
        return cards
    
    def get_card_symbol(self, card_name):
        """Получение символа для карты"""
        symbols = {
            "Маг": "⚡", "Верховная Жрица": "🌙", "Императрица": "🌸",
            "Император": "👑", "Иерофант": "📿", "Влюбленные": "💞",
            "Колесница": "🛡️", "Сила": "🦁", "Отшельник": "🕯️",
            "Колесо Фортуны": "🔄", "Справедливость": "⚖️", "Повешенный": "🙏",
            "Смерть": "🦋", "Умеренность": "⚗️", "Дьявол": "😈",
            "Башня": "⚡", "Звезда": "⭐", "Луна": "🌙",
            "Солнце": "☀️", "Суд": "🎺", "Мир": "🌍", "Шут": "🃏"
        }
        return symbols.get(card_name, "🔮")
    
    def perform_spread(self, chat_id, spread_type, question):
        """Проведение расклада"""
        spread = SPREADS.get(spread_type)
        if not spread:
            bot.send_message(chat_id=chat_id, text="🌀 Такого расклада пока нет.")
            return
        
        # Рисуем карты
        cards = self.draw_cards(spread["cards"])
        
        # Формируем сообщение
        cards_text = f"""✨ *Карты выпали!*

*Вопрос:* {question}
*Расклад:* {spread['name']}

"""
        
        for i, (position, card) in enumerate(zip(spread["positions"], cards)):
            cards_text += f"\n{position}: *{card['name']}* {card['symbol']}"
            if card['reversed']:
                cards_text += " (перевернута)"
            cards_text += f"\n_{card['meaning']}_\n"
        
        bot.send_message(
            chat_id=chat_id,
            text=cards_text,
            parse_mode='Markdown'
        )
        
        # Добавляем интерпретацию
        interpretation = self.get_tarot_interpretation(question, spread_type, cards)
        bot.send_message(
            chat_id=chat_id,
            text=f"🔍 *Интерпретация:*\n\n{interpretation}",
            parse_mode='Markdown'
        )
    
    def get_tarot_interpretation(self, question, spread_type, cards):
        """Получение интерпретации от DeepSeek"""
        try:
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            # Подготавливаем описание карт
            cards_description = ""
            spread = SPREADS[spread_type]
            
            for i, (position, card) in enumerate(zip(spread["positions"], cards)):
                cards_description += f"\n{position}: {card['name']} ({'перевернута' if card['reversed'] else 'прямая'}) - {card['meaning']}"
            
            system_prompt = f"""Ты - опытный таролог. Интерпретируй расклад Таро.

Вопрос: {question}
Расклад: {spread['name']}

Карты:{cards_description}

Дай глубокую, но практическую интерпретацию. Будь мудрым и поддерживающим."""
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Интерпретируй этот расклад, пожалуйста."}
                ],
                "temperature": 0.8,
                "max_tokens": 500
            }
            
            response = requests.post('https://api.deepseek.com/v1/chat/completions', 
                                   headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content']
            
            return "Карты говорят о необходимости доверять своей интуиции. Прислушайся к внутреннему голосу."
                
        except Exception as e:
            logger.error(f"Error getting tarot interpretation: {e}")
            return "Мудрость карт приходит через тишину. Дай себе время почувствовать их послание."
    
    def get_deepseek_response(self, user_message, user_id):
        """Получение ответа от DeepSeek"""
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
                "max_tokens": 400
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
            return "🌀 Произошла ошибка. Попробуй еще раз."
    
    async def process_message(self, update, context):
        """Обработка сообщений"""
        try:
            user_message = update.message.text
            user_id = update.message.from_user.id
            chat_id = update.message.chat_id
            
            if user_message == '/start':
                self.send_welcome_message(chat_id)
            elif user_message == '/tarot':
                self.send_session_start(chat_id)
            elif user_message == '/help':
                help_text = """🔮 *Команды Таро-бота:*

/start - Начало работы
/tarot - Начать сессию Таро
/help - Помощь

💫 Просто напиши вопрос, и я помогу!"""
                await context.bot.send_message(chat_id=chat_id, text=help_text, parse_mode='Markdown')
            elif user_id in self.user_questions:
                # Если есть активный вопрос, делаем расклад
                spread_type = "past_present_future"  # простой расклад по умолчанию
                self.perform_spread(chat_id, spread_type, user_message)
                if user_id in self.user_questions:
                    del self.user_questions[user_id]
            else:
                # Обычный разговор
                response = self.get_deepseek_response(user_message, user_id)
                await context.bot.send_message(chat_id=chat_id, text=response)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def handle_callback(self, update, context):
        """Обработка callback-ов"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "start_session":
            self.send_session_start(query.message.chat_id)
            self.user_questions[query.from_user.id] = True

# Инициализация бота
if BOT_TOKEN:
    from telegram import Bot
    from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler
    
    # Создаем бота и приложение
    bot = Bot(token=BOT_TOKEN)
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Инициализируем логику бота
    tarot_master = TarotMasterBot()
    
    # Добавляем обработчики
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tarot_master.process_message))
    application.add_handler(CallbackQueryHandler(tarot_master.handle_callback))
    
    # Команды
    async def start_command(update, context):
        await tarot_master.send_welcome_message(update.message.chat_id)
    
    async def tarot_command(update, context):
        await tarot_master.send_session_start(update.message.chat_id)
        tarot_master.user_questions[update.message.from_user.id] = True
    
    async def help_command(update, context):
        help_text = """🔮 *Команды Таро-бота:*

/start - Начало работы
/tarot - Начать сессию Таро
/help - Помощь

💫 Просто напиши вопрос, и я помогу!"""
        await context.bot.send_message(chat_id=update.message.chat_id, text=help_text, parse_mode='Markdown')
    
    application.add_handler(MessageHandler(filters.Regex('^/start$'), start_command))
    application.add_handler(MessageHandler(filters.Regex('^/tarot$'), tarot_command))
    application.add_handler(MessageHandler(filters.Regex('^/help$'), help_command))
    
    logger.info("✅ Bot initialized successfully")
else:
    logger.warning("⚠️ BOT_TOKEN not set. Bot functionality disabled.")

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        try:
            if not application:
                return jsonify({"error": "Bot not configured"}), 400
            
            # Обрабатываем обновление
            update = Update.de_json(request.get_json(force=True), application.bot)
            application.update_queue.put(update)
            
            return jsonify({"status": "success"}), 200
            
        except Exception as e:
            logger.error(f"Error in webhook: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/yookassa-webhook', methods=['POST'])
def yookassa_webhook():
    try:
        event_json = request.get_json()
        logger.info(f"Yookassa webhook: {event_json}")
        
        event_type = event_json.get('event')
        payment_data = event_json.get('object', {})
        
        if event_type == 'payment.succeeded':
            metadata = payment_data.get('metadata', {})
            user_id = metadata.get('user_id')
            plan_type = metadata.get('plan_type')
            
            if user_id and plan_type:
                logger.info(f"✅ Payment succeeded for user {user_id}, plan: {plan_type}")
                
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Yookassa webhook error: {e}")
        return jsonify({"status": "error"}), 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook (вызовите этот URL после деплоя)"""
    try:
        if not bot:
            return "Bot not configured", 400
        
        # Получаем URL из запроса или используем Render URL
        webhook_url = request.args.get('url', request.host_url + 'webhook')
        
        # Устанавливаем webhook
        bot.set_webhook(url=webhook_url)
        
        return f"Webhook set to: {webhook_url}", 200
    except Exception as e:
        return f"Error: {e}", 400

@app.route('/')
def home():
    return jsonify({
        "status": "healthy", 
        "bot": "Tarot Master 🔮",
        "version": "1.0",
        "webhook_set": bot.get_webhook_info().url if bot else False
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    # Если запускаем локально, запускаем polling
    if os.environ.get('RENDER', None) is None and application:
        # Локально используем polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        # На Render запускаем Flask
        app.run(host='0.0.0.0', port=port, debug=False)
