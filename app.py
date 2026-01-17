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
from utils import TarotUtils, SubscriptionPlans

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID', 'test_shop_id')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY', 'test_secret_key')

if not BOT_TOKEN:
    bot = None
else:
    from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Dispatcher, MessageHandler, Filters, CallbackQueryHandler
    from telegram.utils.request import Request
    request_obj = Request(con_pool_size=8)
    bot = Bot(token=BOT_TOKEN, request=request_obj)

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

# Стикеры
STICKERS = {
    'mystic': ['CAACAgIAAxkBAAEDLZFl6ScS5rnyU49SD8X83tK0NSj-kAACXxkAAkLjGUvj7-Px9gU_-TUE'],
    'crystal': ['CAACAgIAAxkBAAEDLZVl6SdLIwn6gAJW8wU_y1I0qI-ovAACXhgAAp60EUvJNlI5BRmlqjUE'],
    'moon': ['CAACAgIAAxkBAAEDLZdl6SdZ0fIplYz0R4XgRg5HHtoVnwACbBkAAk3gEEtoSXRhfYt3-jUE']
}

# Расклады Таро
SPREADS = {
    "past_present_future": {
        "name": "Прошлое-Настоящее-Будущее",
        "cards": 3,
        "positions": ["Прошлое", "Настоящее", "Будущее"],
        "description": "Классический расклад для понимания временных линий"
    },
    "celtic_cross": {
        "name": "Кельтский Крест",
        "cards": 10,
        "positions": ["Сердце ситуации", "Препятствие", "Сознательные цели", "Бессознательные влияния", 
                     "Прошлое", "Ближайшее будущее", "Ваше отношение", "Внешние влияния", 
                     "Надежды и страхи", "Итог"],
        "description": "Глубокий анализ ситуации со всех сторон"
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

class TarotMasterBot:
    def __init__(self):
        self.personality = """
        Ты - мудрый таролог и духовный наставник по имени Ариэль, 35 лет. 
        Обладаешь глубокими знаниями в области Таро, психологии и духовных практик.
        Твой стиль - мудрый, заботливый, немного мистический, но приземленный.
        """
        self.active_spreads = {}
        self.user_questions = {}
        
        # Запускаем ежедневные советы
        self.start_daily_insights()
    
    def start_daily_insights(self):
        """Ежедневные мистические советы"""
        def insights_loop():
            while True:
                try:
                    now = datetime.now()
                    if now.hour == 10 and now.minute == 0:
                        active_users = self.get_active_users()
                        for user_id in active_users:
                            try:
                                insight = self.generate_daily_insight()
                                bot.send_message(chat_id=user_id, text=insight)
                                logger.info(f"🔮 Sent daily insight to user {user_id}")
                            except Exception as e:
                                logger.error(f"Error sending insight: {e}")
                        time.sleep(3600)  # Ждем час чтобы не повторять
                    time.sleep(60)  # Проверяем каждую минуту
                except Exception as e:
                    logger.error(f"Error in insights loop: {e}")
                    time.sleep(300)
        
        thread = threading.Thread(target=insights_loop, daemon=True)
        thread.start()
    
    def generate_daily_insight(self):
        """Генерация ежедневного совета"""
        card = random.choice(list(TAROT_DECK.keys()))
        meaning = TAROT_DECK[card]["meaning"]
        return f"🌙 *Карта дня:* {card}\n\n{meaning}\n\nСегодня доверяй своей интуиции."
    
    def get_active_users(self):
        """Получение активных пользователей"""
        try:
            session = SessionLocal()
            active_subs = session.query(UserSubscription).filter(
                UserSubscription.expires_at > datetime.now()
            ).all()
            session.close()
            return [sub.user_id for sub in active_subs]
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
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
                "reversed": is_reversed
            })
        return cards
    
    def process_message(self, update, context):
        """Обработка сообщений"""
        try:
            user_message = update.message.text
            user_id = update.message.from_user.id
            chat_id = update.message.chat_id
            
            if user_message == '/start':
                self.send_welcome_message(chat_id)
            elif user_message == '/tarot':
                self.send_session_start(chat_id)
            elif user_message == '/insight':
                insight = self.generate_daily_insight()
                bot.send_message(chat_id=chat_id, text=insight, parse_mode='Markdown')
            else:
                response = self.get_deepseek_response(user_message, user_id)
                bot.send_message(chat_id=chat_id, text=response)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def send_welcome_message(self, chat_id):
        """Приветственное сообщение"""
        welcome_text = """🔮 *Добро пожаловать в Храм Мудрости Таро!*

Я - Ариэль, твой проводник в мир символов и инсайтов."""
        
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

Сформулируй свой вопрос:"""
        bot.send_message(chat_id=chat_id, text=session_text, parse_mode='Markdown')
    
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
                return data['choices'][0]['message']['content']
            return "🌀 Энергия сегодня рассеяна. Попробуй позже."
                
        except Exception as e:
            logger.error(f"Error calling DeepSeek: {e}")
            return "🌀 Произошла ошибка. Попробуй еще раз."
    
    def handle_callback(self, update, context):
        """Обработка callback-ов"""
        query = update.callback_query
        query.answer()
        
        if query.data == "start_session":
            self.send_session_start(query.message.chat_id)

# Инициализация бота
tarot_master = TarotMasterBot()

# Создаем диспетчер
if bot:
    from telegram.ext import Dispatcher, MessageHandler, Filters, CallbackQueryHandler
    dp = Dispatcher(bot, None, workers=0, use_context=True)
    dp.add_handler(MessageHandler(Filters.text, tarot_master.process_message))
    dp.add_handler(CallbackQueryHandler(tarot_master.handle_callback))

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        try:
            if not bot:
                return jsonify({"error": "Bot not configured"}), 400
            
            from telegram import Update
            update = Update.de_json(request.get_json(), bot)
            dp.process_update(update)
            return jsonify({"status": "success"}), 200
            
        except Exception as e:
            logger.error(f"Error in webhook: {e}")
            return jsonify({"status": "error"}), 400

@app.route('/')
def home():
    return jsonify({
        "status": "healthy", 
        "bot": "Tarot Master 🔮"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
