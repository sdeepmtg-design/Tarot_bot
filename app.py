from flask import Flask, request, jsonify
import os
import requests
import logging
import random
import time
import threading
import hashlib

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

# Глобальные хранилища
conversations = {}
user_first_messages = {}
message_history = {}
processed_messages = set()  # Для дедупликации
last_message_time = {}

# Очищаем старые processed_messages каждые 5 минут
def cleanup_processed_messages():
    while True:
        time.sleep(300)  # 5 минут
        # Удаляем старые хеши (старше 10 минут)
        cutoff = time.time() - 600
        # Немного сложно, так как мы храним только хеши
        # Вместо этого просто очищаем периодически
        if len(processed_messages) > 1000:
            processed_messages.clear()
            logger.info("🧹 Очищена история processed_messages")

threading.Thread(target=cleanup_processed_messages, daemon=True).start()

def get_message_hash(chat_id, message_text, update_id=None):
    """Создает уникальный хеш для сообщения"""
    content = f"{chat_id}_{message_text}"
    if update_id:
        content += f"_{update_id}"
    return hashlib.md5(content.encode()).hexdigest()

def is_message_processed(message_hash):
    """Проверяет, обрабатывалось ли уже это сообщение"""
    return message_hash in processed_messages

def mark_message_processed(message_hash):
    """Отмечает сообщение как обработанное"""
    processed_messages.add(message_hash)

def show_typing(chat_id, duration=None):
    """Показывает статус 'печатает'"""
    if duration is None:
        duration = random.uniform(2.0, 4.0)
    
    def typing_action():
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction"
            payload = {'chat_id': chat_id, 'action': 'typing'}
            requests.post(url, json=payload, timeout=5)
            time.sleep(duration)
        except:
            pass
    
    threading.Thread(target=typing_action, daemon=True).start()

def get_human_delay():
    """Задержка 60-180 секунд (1-3 минуты)"""
    return random.randint(60, 180)

def send_message_with_delay(chat_id, text, delay_override=None):
    """Отправляет сообщение с задержкой"""
    def send():
        if delay_override:
            delay = delay_override
        else:
            delay = get_human_delay()
        
        logger.info(f"⏰ Задержка: {delay} сек для: {text[:40]}...")
        time.sleep(delay)
        
        show_typing(chat_id, duration=random.uniform(1.5, 3.0))
        time.sleep(random.uniform(1.5, 3.0))
        
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ Ошибка отправки: {response.text}")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
    
    threading.Thread(target=send, daemon=True).start()

def send_multiple_messages(chat_id, messages):
    """Отправляет несколько сообщений с паузами"""
    def send_sequence():
        for i, msg in enumerate(messages):
            if i > 0:
                pause = random.randint(10, 25)
                logger.info(f"⏸️ Пауза между сообщениями: {pause} сек")
                time.sleep(pause)
            
            show_typing(chat_id, duration=random.uniform(1.5, 3.0))
            time.sleep(random.uniform(1.5, 3.0))
            
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'}
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code != 200:
                    logger.error(f"❌ Ошибка отправки сообщения: {response.text}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
    
    threading.Thread(target=send_sequence, daemon=True).start()

def get_conversation_state(chat_id):
    """Получает или создает состояние диалога"""
    if chat_id not in conversations:
        conversations[chat_id] = {
            'stage': 'awaiting_problem',  # Ждем проблему
            'user_name': '',
            'problem': '',
            'problem_type': '',
            'trust_level': 0,
            'message_count': 0,
            'last_message_time': time.time(),
            'payment_offered': False,
            'payment_link_sent': False,
            'waiting_for_payment': False,
            'conversation_start': time.time(),
            'greeted': False,
            'last_responses': [],  # Последние отправленные ответы
            'message_queue': []  # Очередь сообщений для отправки
        }
    
    conversations[chat_id]['last_message_time'] = time.time()
    return conversations[chat_id]

def add_to_response_history(chat_id, response_text):
    """Добавляет ответ в историю"""
    if 'last_responses' not in conversations[chat_id]:
        conversations[chat_id]['last_responses'] = []
    
    conversations[chat_id]['last_responses'].append({
        'text': response_text[:50],  # Сохраняем только начало для логов
        'time': time.time()
    })
    
    # Ограничиваем историю 10 последними ответами
    if len(conversations[chat_id]['last_responses']) > 10:
        conversations[chat_id]['last_responses'] = conversations[chat_id]['last_responses'][-10:]

def is_response_recent(chat_id, response_text):
    """Проверяет, отправлялся ли похожий ответ недавно"""
    if chat_id not in conversations or 'last_responses' not in conversations[chat_id]:
        return False
    
    current_time = time.time()
    for resp in conversations[chat_id]['last_responses']:
        # Если тот же ответ был отправлен менее 5 минут назад
        if (current_time - resp['time'] < 300 and 
            response_text[:30] == resp['text'][:30]):  # Сравниваем начало
            return True
    
    return False

def get_unique_response(responses, chat_id):
    """Возвращает уникальный ответ, который не отправлялся недавно"""
    if not responses:
        return ""
    
    # Пытаемся найти ответ, который не отправлялся недавно
    for attempt in range(3):  # 3 попытки
        response = random.choice(responses)
        if not is_response_recent(chat_id, response):
            return response
    
    # Если все отправлялись недавно, берем любой
    return random.choice(responses)

def format_message(text, is_fast=False):
    """Форматирует сообщение естественно"""
    if is_fast and len(text) < 100:
        if random.random() < 0.7 and text:
            text = text[0].lower() + text[1:]
        
        if random.random() < 0.5 and text.endswith('.'):
            text = text[:-1]
    
    if random.random() < 0.4 and ", что" in text:
        text = text.replace(", что", " что")
    
    return text

def is_problem_message(message):
    """Определяет, является ли сообщение описанием проблемы"""
    if not message or len(message) < 10:
        return False
    
    message_lower = message.lower()
    
    # Игнорируем команды
    if message_lower.startswith('/'):
        return False
    
    problem_keywords = [
        'не могу', 'не знаю', 'проблем', 'ситуац', 'трудност', 'сложност', 
        'боюсь', 'страшно', 'волнуюсь', 'переживаю', 'хочу понять', 
        'как быть', 'что делать', 'помогите', 'совет', 'мне нужн', 'у меня',
        'хочу узнать', 'интересно', 'скажите', 'подскажите'
    ]
    
    # Проверяем наличие ключевых слов
    for keyword in problem_keywords:
        if keyword in message_lower:
            return True
    
    # Проверяем вопросительные предложения
    if '?' in message and len(message) > 15:
        return True
    
    return False

def analyze_problem_type(message):
    """Анализирует тип проблемы"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ['девушк', 'парн', 'мужчин', 'женщин', 'любов', 'отношен', 'семь', 'брак']):
        return 'отношения'
    elif any(word in message_lower for word in ['работ', 'карьер', 'начальник', 'коллег', 'зарплат', 'офис', 'проект']):
        return 'работа'
    elif any(word in message_lower for word in ['деньг', 'финанс', 'долг', 'кредит', 'заработ', 'бизнес', 'куп']):
        return 'деньги'
    elif any(word in message_lower for word in ['здоров', 'болезн', 'боль', 'врач', 'лечен', 'энерг', 'устал']):
        return 'здоровье'
    elif any(word in message_lower for word in ['выбор', 'решен', 'сомнен', 'не уверен', 'не знаю как']):
        return 'выбор'
    else:
        return 'общая'

def generate_greeting_response(user_name, state):
    """Генерирует приветственный ответ"""
    if state['greeted']:
        # Уже поздоровались, возвращаем пустой список
        return []
    
    state['greeted'] = True
    greetings = [
        f"привет, {user_name} ✨",
        f"здравствуй, {user_name}",
        f"{user_name}, приветствую"
    ]
    
    greeting = get_unique_response(greetings, state.get('chat_id'))
    
    prompts = [
        "расскажи, что привело тебя сегодня",
        "что на душе",
        "чем могу помочь"
    ]
    
    prompt = random.choice(prompts)
    
    return [
        format_message(greeting, False),
        format_message(prompt, False)
    ]

def generate_problem_response(problem_text, user_name, state):
    """Генерирует ответ на проблему"""
    problem_type = analyze_problem_type(problem_text)
    state['problem'] = problem_text
    state['problem_type'] = problem_type
    state['stage'] = 'problem_understood'
    
    # Эмпатичные ответы по типам
    empathy_responses = {
        'отношения': [
            f"понимаю, {user_name}... сердечные вопросы всегда такие глубокие",
            f"ой, {user_name}, отношения... это всегда про самое важное",
            f"чувствую, {user_name}, как это важно для тебя"
        ],
        'работа': [
            f"{user_name}, рабочие вопросы часто бывают очень напряженными",
            f"понимаю, {user_name}... работа действительно может выматывать",
            f"чувствую напряжение, {user_name}"
        ],
        'деньги': [
            f"{user_name}, финансовые темы часто связаны с безопасностью",
            f"понимаю твою озабоченность, {user_name}",
            f"{user_name}, деньги... это всегда про свободу и возможности"
        ],
        'здоровье': [
            f"{user_name}, здоровье - это основа",
            f"чувствую твою заботу о себе, {user_name}",
            f"понимаю, {user_name}, как это важно"
        ],
        'выбор': [
            f"{user_name}, стоять на распутье... это всегда непросто",
            f"чувствую твои сомнения, {user_name}",
            f"{user_name}, моменты выбора часто определяют многое"
        ],
        'общая': [
            f"слышу тебя, {user_name}",
            f"понимаю, {user_name}",
            f"чувствую, как это беспокоит тебя, {user_name}"
        ]
    }
    
    empathy = get_unique_response(empathy_responses[problem_type], state.get('chat_id'))
    
    # Вопросы для углубления
    questions = {
        'отношения': [
            "что самое важное для тебя в этих отношениях",
            "чего не хватает для полного счастья",
            "что твое сердце чувствует в этой ситуации"
        ],
        'работа': [
            "что самое сложное в этой ситуации",
            "как это влияет на твое состояние каждый день",
            "что бы ты хотел изменить в первую очередь"
        ],
        'деньги': [
            "как эта ситуация влияет на твою свободу",
            "чего ты боишься больше всего",
            "что изменится, если деньги перестанут быть проблемой"
        ],
        'здоровье': [
            "как это влияет на твою повседневную жизнь",
            "что говорит тебе твое тело",
            "какой поддержки тебе не хватает"
        ],
        'выбор': [
            "что подсказывает твоя интуиция",
            "чего ты боишься в каждом из вариантов",
            "какой выбор сделало бы твое сердце, если бы не было страха"
        ],
        'общая': [
            "что самое тяжелое в этом для тебя",
            "как долго это с тобой",
            "что бы хотелось изменить"
        ]
    }
    
    question = random.choice(questions[problem_type])
    
    return [
        format_message(empathy, False),
        format_message(question, False)
    ]

def generate_offer_response(user_name, state):
    """Генерирует предложение помощи"""
    state['stage'] = 'offering_help'
    
    offers = [
        f"{user_name}, иногда полезно посмотреть на ситуацию с другой стороны\nкарты таро могут стать таким проводником",
        f"знаешь, {user_name}, карты часто помогают увидеть то, что скрыто\nхочешь попробовать такой диалог",
        f"{user_name}, у меня есть чувство\nчто здесь есть важные подсказки для тебя\nкарты могут помочь их расшифровать"
    ]
    
    offer = get_unique_response(offers, state.get('chat_id'))
    
    explanations = [
        "это не гадание, а разговор с собой через язык символов",
        "это как посмотреть на ситуацию через чистое зеркало",
        "карты помогают увидеть то, что мы часто не замечаем в суете"
    ]
    
    explanation = random.choice(explanations)
    
    return [
        format_message(offer, False),
        format_message(explanation, False)
    ]

def generate_value_response(user_name, state):
    """Генерирует ответ про ценность"""
    state['stage'] = 'discussing_value'
    state['payment_offered'] = True
    
    responses = [
        f"хорошо, {user_name} 💫\nтогда я создам для тебя персональный расклад",
        "буду работать с твоей ситуацией очень внимательно",
        f"стоимость - 1490 рублей\nно для тебя, {user_name}, сделаю за 990",
        "это не просто оплата\nа энергообмен и твоя готовность к изменениям"
    ]
    
    return [format_message(r, False) for r in responses]

def generate_payment_response(user_name, state):
    """Генерирует ответ с оплатой"""
    if not state['payment_link_sent']:
        state['payment_link_sent'] = True
        state['stage'] = 'awaiting_payment'
        
        pre_responses = [
            f"чувствую твою решимость, {user_name} ✨",
            "этот шаг изменит многое для тебя"
        ]
        
        return [
            format_message(random.choice(pre_responses), False),
            "держи ссылку для оплаты",
            "https://yoomoney.ru/to/4100111234567890"  # ЗАМЕНИТЕ!
        ]
    
    return [format_message("ссылка уже отправлена, проверь сообщения выше", False)]

def process_user_message(chat_id, user_name, message_text):
    """Обрабатывает сообщение пользователя"""
    state = get_conversation_state(chat_id)
    state['user_name'] = user_name
    state['message_count'] += 1
    
    logger.info(f"💬 Чат {chat_id}, Стадия: {state['stage']}, Сообщение: {state['message_count']}")
    
    # Определяем тип сообщения
    message_lower = message_text.lower()
    
    # Игнорируем /start и другие команды как отдельные сообщения
    if message_text.startswith('/'):
        if state['message_count'] == 1:  # Первое сообщение - /start
            return generate_greeting_response(user_name, state)
        else:
            return []  # Игнорируем команды в середине диалога
    
    # Основная логика по стадиям
    if state['stage'] == 'awaiting_problem':
        if is_problem_message(message_text):
            return generate_problem_response(message_text, user_name, state)
        else:
            # Если не проблема, все равно переходим к диалогу
            state['stage'] = 'greeting'
            return generate_greeting_response(user_name, state)
    
    elif state['stage'] == 'problem_understood':
        # Пользователь ответил на вопрос о проблеме
        return generate_offer_response(user_name, state)
    
    elif state['stage'] == 'offering_help':
        positive_words = ['да', 'хочу', 'готов', 'соглас', 'интересно', 'можно', 'попробую', 'давай']
        
        if any(word in message_lower for word in positive_words):
            return generate_value_response(user_name, state)
        else:
            # Если сомневается
            comfort = [
                f"всё в твоем ритме, {user_name}",
                "не торопись с решением",
                f"посиди с этим ощущением, {user_name}"
            ]
            return [format_message(random.choice(comfort), False)]
    
    elif state['stage'] == 'discussing_value':
        if 'сколько' in message_lower or 'цена' in message_lower or 'стоимость' in message_lower or '990' in message_lower:
            state['stage'] = 'ready_for_payment'
            return [format_message(f"{user_name}, готов сделать этот шаг к ясности", False)]
        
        elif 'готов' in message_lower or 'куплю' in message_lower or 'оплат' in message_lower:
            return generate_payment_response(user_name, state)
        
        else:
            return [format_message(f"{user_name}, как тебе такая инвестиция в себя", False)]
    
    elif state['stage'] == 'ready_for_payment':
        if any(word in message_lower for word in ['готов', 'давай', 'хочу', 'куплю', 'оплат']):
            return generate_payment_response(user_name, state)
        
        else:
            return [format_message(f"{user_name}, всё в твоем темпе", False)]
    
    elif state['stage'] == 'awaiting_payment':
        if 'оплат' in message_lower or 'перевел' in message_lower or 'сделал' in message_lower or 'оплатил' in message_lower:
            state['stage'] = 'working'
            state['waiting_for_payment'] = False
            
            gratitude = [
                f"благодарю, {user_name} 🙏",
                "энергия пошла",
                "начинаю работать с картами для твоего расклада",
                "займет немного времени\nно оно того стоит\nотдохни, скоро вернусь с ответами"
            ]
            
            return [format_message(r, False) for r in gratitude]
        
        else:
            reminders = [
                f"я здесь, {user_name}\nжду, когда будешь готов",
                "всё в твоем ритме\nссылка ждет тебя"
            ]
            
            return [format_message(random.choice(reminders), False)]
    
    elif state['stage'] == 'working':
        updates = [
            "карты уже говорят...\nчто-то важное про твой путь",
            "вижу интересные связи\nто, что было скрыто",
            f"{user_name}, это глубже, чем кажется"
        ]
        
        return [format_message(random.choice(updates), False)]
    
    # Если непонятная стадия, возвращаем к началу
    state['stage'] = 'awaiting_problem'
    return [format_message(f"{user_name}, расскажи, что происходит", False)]

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной webhook с дедупликацией"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error"}), 400
        
        # Получаем update_id для дедупликации
        update_id = data.get('update_id')
        
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text'].strip()
            chat_id = data['message']['chat']['id']
            user_name = data['message']['from'].get('first_name', 'друг')
            
            # Создаем уникальный хеш сообщения
            message_hash = get_message_hash(chat_id, message_text, update_id)
            
            # Проверяем, не обрабатывали ли уже это сообщение
            if is_message_processed(message_hash):
                logger.info(f"⏭️ Пропускаем дубликат: {message_text[:30]}...")
                return jsonify({"status": "skipped_duplicate"}), 200
            
            # Отмечаем сообщение как обработанное
            mark_message_processed(message_hash)
            
            logger.info(f"👤 {user_name}: {message_text}")
            
            # Показываем печать
            show_typing(chat_id)
            
            # Обрабатываем сообщение
            responses = process_user_message(chat_id, user_name, message_text)
            
            # Отправляем ответы
            if responses:
                # Добавляем ответы в историю
                state = get_conversation_state(chat_id)
                for resp in responses:
                    add_to_response_history(chat_id, resp)
                
                if len(responses) == 1:
                    send_message_with_delay(chat_id, responses[0])
                else:
                    send_multiple_messages(chat_id, responses)
            
            return jsonify({"status": "success"}), 200
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"🚨 Ошибка: {e}")
        return jsonify({"status": "error"}), 400

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook"""
    try:
        if not BOT_TOKEN:
            return jsonify({"error": "BOT_TOKEN не установлен"}), 400
        
        webhook_url = request.host_url.rstrip('/') + '/webhook'
        telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.post(telegram_url, json={'url': webhook_url})
        
        return jsonify({
            "success": response.status_code == 200,
            "webhook_url": webhook_url
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/debug', methods=['GET'])
def debug():
    """Страница отладки"""
    chat_id = request.args.get('chat_id')
    
    if chat_id and chat_id in conversations:
        state = conversations[chat_id]
        return jsonify({
            "chat_id": chat_id,
            "state": state,
            "message_history": message_history.get(chat_id, {}),
            "processed_messages_count": len(processed_messages)
        })
    
    return jsonify({
        "active_chats": len(conversations),
        "processed_messages": len(processed_messages),
        "message_history_size": sum(len(v) for v in message_history.values())
    })

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "bot": "@Tarotyour_bot",
        "description": "Бот-таролог с дедупликацией сообщений",
        "features": [
            "Дедупликация дублирующих сообщений",
            "Не повторяет одинаковые ответы",
            "Задержки 1-3 минуты",
            "Начинает с любого сообщения"
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info("🚀 Бот запущен с дедупликацией сообщений")
    logger.info("🛡️ Защита от дублирующих webhook-запросов")
    logger.info("🔄 Уникальные ответы без повторов")
    app.run(host='0.0.0.0', port=port, debug=False)
