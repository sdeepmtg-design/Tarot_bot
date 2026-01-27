from flask import Flask, request, jsonify
import os
import requests
import logging
import random
import time
import threading
from datetime import datetime, timedelta

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
last_message_time = {}

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
        
        logger.info(f"⏰ Задержка: {delay} сек")
        time.sleep(delay)
        
        show_typing(chat_id, duration=random.uniform(1.5, 3.0))
        time.sleep(random.uniform(1.5, 3.0))
        
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
    
    threading.Thread(target=send, daemon=True).start()

def send_multiple_messages(chat_id, messages):
    """Отправляет несколько сообщений с паузами"""
    def send_sequence():
        for i, msg in enumerate(messages):
            if i > 0:
                pause = random.randint(10, 25)
                time.sleep(pause)
            
            show_typing(chat_id, duration=random.uniform(1.5, 3.0))
            time.sleep(random.uniform(1.5, 3.0))
            
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'}
                requests.post(url, json=payload, timeout=10)
            except:
                pass
    
    threading.Thread(target=send_sequence, daemon=True).start()

def is_first_message(chat_id, message_text):
    """Проверяет, первое ли это сообщение от пользователя"""
    if chat_id not in user_first_messages:
        user_first_messages[chat_id] = {
            'first_message': message_text,
            'received_at': time.time(),
            'processed': False
        }
        return True
    return False

def mark_first_message_processed(chat_id):
    """Отмечает первое сообщение как обработанное"""
    if chat_id in user_first_messages:
        user_first_messages[chat_id]['processed'] = True

def get_conversation_state(chat_id):
    """Получает или создает состояние диалога"""
    if chat_id not in conversations:
        conversations[chat_id] = {
            'stage': 'problem_received',  # Начинаем сразу с получения проблемы
            'user_name': '',
            'problem': '',
            'trust_level': 0,
            'message_count': 0,
            'last_message_time': time.time(),
            'payment_offered': False,
            'payment_link_sent': False,
            'waiting_for_payment': False,
            'last_responses': [],
            'conversation_start': time.time(),
            'greeted': False  # Флаг, что уже поздоровались
        }
    
    conversations[chat_id]['last_message_time'] = time.time()
    conversations[chat_id]['message_count'] += 1
    
    return conversations[chat_id]

def get_unique_response(responses, chat_id, used_responses_key='general'):
    """Возвращает уникальный ответ"""
    if chat_id not in message_history:
        message_history[chat_id] = {}
    
    if used_responses_key not in message_history[chat_id]:
        message_history[chat_id][used_responses_key] = []
    
    # Ищем неиспользованные ответы
    unused = [r for r in responses if r not in message_history[chat_id][used_responses_key]]
    
    if unused:
        response = random.choice(unused)
    else:
        # Если все использовались, берем любой
        response = random.choice(responses)
    
    # Сохраняем в историю (максимум 10 последних)
    message_history[chat_id][used_responses_key].append(response)
    if len(message_history[chat_id][used_responses_key]) > 10:
        message_history[chat_id][used_responses_key] = message_history[chat_id][used_responses_key][-10:]
    
    return response

def format_message(text, is_fast=False):
    """Форматирует сообщение естественно"""
    if is_fast and len(text) < 100:
        if random.random() < 0.7:
            text = text[0].lower() + text[1:] if text else text
        
        if random.random() < 0.5 and text.endswith('.'):
            text = text[:-1]
    
    # Убираем запятую перед "что"
    if random.random() < 0.4 and ", что" in text:
        text = text.replace(", что", " что")
    
    # Случайный сленг
    if random.random() < 0.15:
        replacements = {
            'понимаю': ['понимаю', 'ясно', 'чувствую'][random.randint(0, 2)],
            'спасибо': ['спасибо', 'спс'][random.randint(0, 1)],
            'конечно': ['конечно', 'разумеется'][random.randint(0, 1)]
        }
        
        for formal, informal in replacements.items():
            if formal in text.lower():
                text = text.replace(formal, informal)
                break
    
    return text

def is_problem_message(message):
    """Определяет, является ли сообщение описанием проблемы"""
    message_lower = message.lower()
    
    # Признаки проблемы
    problem_keywords = ['не могу', 'не знаю', 'проблем', 'ситуац', 'трудност', 'сложност', 
                       'боюсь', 'страшно', 'волнуюсь', 'переживаю', 'хочу понять', 
                       'как быть', 'что делать', 'помогите', 'совет', 'мне нужн', 'у меня']
    
    # Минимальная длина для проблемы
    if len(message) < 15:
        return False
    
    # Проверяем наличие ключевых слов
    for keyword in problem_keywords:
        if keyword in message_lower:
            return True
    
    # Проверяем вопросительные предложения
    if '?' in message and len(message) > 20:
        return True
    
    return False

def analyze_problem_type(message):
    """Анализирует тип проблемы"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ['работ', 'карьер', 'начальник', 'коллег', 'зарплат', 'офис']):
        return 'работа'
    elif any(word in message_lower for word in ['отношен', 'любов', 'муж', 'жена', 'парень', 'девушка', 'семь', 'брак']):
        return 'отношения'
    elif any(word in message_lower for word in ['деньг', 'финанс', 'долг', 'кредит', 'заработ', 'бизнес']):
        return 'деньги'
    elif any(word in message_lower for word in ['здоров', 'болезн', 'боль', 'врач', 'лечен', 'энерг']):
        return 'здоровье'
    elif any(word in message_lower for word in ['выбор', 'решен', 'не знаю как', 'сомнен', 'не уверен']):
        return 'выбор'
    else:
        return 'общая'

def generate_problem_response(problem_text, user_name, state):
    """Генерирует ответ на проблему"""
    problem_type = analyze_problem_type(problem_text)
    state['problem'] = problem_text
    state['problem_type'] = problem_type
    
    # Эмпатичные ответы на разные типы проблем
    empathy_by_type = {
        'работа': [
            f"понимаю, {user_name}... рабочие вопросы часто бывают очень заряженными\nчувствую напряжение в твоих словах",
            f"{user_name}, работа действительно может выматывать\nособенно когда там сложные отношения или задачи"
        ],
        'отношения': [
            f"ой, {user_name}... отношения всегда затрагивают самые глубокие струны души\nчувствую, как это важно для тебя",
            f"{user_name}, сердечные вопросы... они всегда такие хрупкие и значимые\nспасибо, что делишься этим"
        ],
        'деньги': [
            f"{user_name}, денежные темы часто связаны с безопасностью и свободой\nпонимаю твою озабоченность",
            f"чувствую, {user_name}, как финансы влияют на твоё состояние\nэто действительно важно"
        ],
        'здоровье': [
            f"{user_name}, здоровье - основа всего\nчувствую твою заботу о себе, это прекрасно",
            f"понимаю, {user_name}\nкогда тело или энергия дают сбой - это сигнал для внимания"
        ],
        'выбор': [
            f"{user_name}, стоять на распутье... это всегда непросто\nчувствую твои сомнения",
            f"{user_name}, моменты выбора часто определяют многое\nпонимаю важность этого для тебя"
        ],
        'общая': [
            f"слышу тебя, {user_name}\nчувствую, как это беспокоит тебя",
            f"{user_name}, понимаю\nтакое бывает, когда ситуация кажется безвыходной"
        ]
    }
    
    empathy = get_unique_response(empathy_by_type[problem_type], state.get('chat_id'), 'empathy')
    
    # Вопросы для углубления
    deepening_questions = {
        'работа': [
            "а что самое сложное в этой рабочей ситуации",
            "как это влияет на твоё состояние каждый день",
            "что бы ты хотел изменить в первую очередь"
        ],
        'отношения': [
            "а что твоё сердце чувствует в этой ситуации",
            "чего не хватает в этих отношениях для счастья",
            "что самое болезненное в этом"
        ],
        'деньги': [
            "как эта финансовая ситуация влияет на твою свободу",
            "что бы изменилось, если бы деньги перестали быть проблемой",
            "чего ты боишься больше всего в этом"
        ],
        'здоровье': [
            "как это влияет на твою повседневную жизнь",
            "что говорит тебе твое тело через эту ситуацию",
            "какой поддержки тебе не хватает"
        ],
        'выбор': [
            "а что подсказывает твоя интуиция",
            "чего ты боишься в каждом из вариантов",
            "какой выбор сделало бы твое сердце, если бы не было страха"
        ],
        'общая': [
            "а что самое тяжелое в этом для тебя",
            "как долго это с тобой",
            "что бы хотелось изменить в первую очередь"
        ]
    }
    
    question = get_unique_response(deepening_questions[problem_type], state.get('chat_id'), 'questions')
    
    return [
        format_message(empathy, False),
        format_message(question, False)
    ]

def generate_followup_response(user_message, user_name, state):
    """Генерирует ответ на продолжение диалога"""
    message_lower = user_message.lower()
    stage = state['stage']
    
    # Если пользователь отвечает на вопрос о проблеме
    if stage == 'problem_received':
        state['stage'] = 'offering_help'
        state['trust_level'] += 1
        
        # Предложение помощи
        offerings = [
            f"{user_name}, чувствую, что здесь есть что исследовать\n\nкарты таро могут помочь увидеть то, что не очевидно",
            f"понимаю, {user_name}\n\nиногда полезно посмотреть на ситуацию через призму символов\nкарты могут дать неожиданные подсказки",
            f"{user_name}, у меня есть чувство\nчто в этой ситуации скрыты важные уроки\n\nхотите, чтобы я сделала расклад и помогла их увидеть"
        ]
        
        offering = get_unique_response(offerings, state.get('chat_id'), 'offering')
        
        return [
            format_message("мм, понимаю...", False),
            format_message(offering, False),
            format_message("это не гадание, а глубокий анализ ситуации\nчерез язык карт и интуиции", False)
        ]
    
    # Если предлагаем помощь
    elif stage == 'offering_help':
        positive_words = ['да', 'хочу', 'готов', 'соглас', 'интересно', 'можно', 'попробую', 'почему нет', 'давай']
        
        if any(word in message_lower for word in positive_words):
            state['stage'] = 'discussing_value'
            state['payment_offered'] = True
            
            return [
                format_message(f"хорошо, {user_name} 💫", False),
                format_message("тогда я создам для тебя персональный расклад", False),
                format_message("буду работать с твоей ситуацией очень внимательно", False),
                format_message("стоимость - 1490 рублей\nно для тебя, {user_name}, сделаю за 990".format(user_name=user_name), False),
                format_message("это не просто оплата\nа энергообмен и твоя готовность к изменениям", False)
            ]
        else:
            # Если ещё не готов
            state['stage'] = 'understanding_doubt'
            
            comfort = [
                f"всё в твоем ритме, {user_name}",
                "не торопись с решением",
                f"посиди с этим ощущением, {user_name}\nоно тебе что-то говорит"
            ]
            
            response = get_unique_response(comfort, state.get('chat_id'), 'comfort')
            return [format_message(response, False)]
    
    # Если обсуждаем ценность
    elif stage == 'discussing_value':
        if 'сколько' in message_lower or 'цена' in message_lower or 'стоимость' in message_lower or '990' in message_lower:
            state['stage'] = 'asking_readiness'
            
            readiness = [
                f"{user_name}, как тебе такая инвестиция в себя\n990 рублей за ясность и новые перспективы",
                f"чувствую, это доступная сумма для важного шага\n{user_name}, ты так не считаешь"
            ]
            
            response = get_unique_response(readiness, state.get('chat_id'), 'readiness')
            return [format_message(response, False)]
        
        elif 'готов' in message_lower or 'куплю' in message_lower or 'оплат' in message_lower:
            state['stage'] = 'sending_link'
            
            return [
                format_message(f"чувствую твою решимость, {user_name} ✨", False),
                format_message("этот шаг изменит многое для тебя", False)
            ]
        
        else:
            state['stage'] = 'asking_readiness'
            return [format_message(f"{user_name}, готов сделать этот шаг к ясности", False)]
    
    # Если спрашиваем о готовности
    elif stage == 'asking_readiness':
        if any(word in message_lower for word in ['готов', 'давай', 'хочу', 'куплю', 'оплат']):
            state['stage'] = 'sending_link'
            state['waiting_for_payment'] = True
            
            return [
                format_message(f"отлично, {user_name} 🌟", False),
                format_message("чувствую, как энергия двигается", False)
            ]
        
        else:
            return [format_message(f"{user_name}, всё в твоем темпе\nпросто скажи, когда будешь готов", False)]
    
    # Если отправляем ссылку
    elif stage == 'sending_link' and not state['payment_link_sent']:
        state['payment_link_sent'] = True
        state['stage'] = 'awaiting_payment'
        
        payment_url = "https://yoomoney.ru/to/4100111234567890"  # ЗАМЕНИТЕ!
        
        return [
            "держи ссылку для оплаты",
            payment_url
        ]
    
    # Если ожидаем оплату
    elif stage == 'awaiting_payment':
        if 'оплат' in message_lower or 'перевел' in message_lower or 'сделал' in message_lower or 'оплатил' in message_lower:
            state['stage'] = 'working'
            state['waiting_for_payment'] = False
            
            return [
                format_message(f"благодарю, {user_name} 🙏", False),
                format_message("энергия пошла", False),
                format_message("начинаю работать с картами\nдля твоего расклада", False),
                format_message("займет немного времени\nно оно того стоит\n\nотдохни, скоро вернусь с ответами", False)
            ]
        
        elif not state['payment_link_sent']:
            state['stage'] = 'sending_link'
            return ["дай секунду, пришлю ссылку"]
        
        else:
            reminders = [
                f"я здесь, {user_name}\nжду, когда будешь готов",
                "всё в твоем ритме\nссылка ждет тебя"
            ]
            
            response = get_unique_response(reminders, state.get('chat_id'), 'reminders')
            return [format_message(response, False)]
    
    # Если работаем над раскладом
    elif stage == 'working':
        updates = [
            "карты уже говорят...\nчто-то важное про твой путь",
            "вижу интересные связи\nто, что было скрыто",
            f"{user_name}, это глубже, чем кажется\nи прекраснее тоже"
        ]
        
        response = get_unique_response(updates, state.get('chat_id'), 'updates')
        return [format_message(response, False)]
    
    # Если понимаем сомнения
    elif stage == 'understanding_doubt':
        if any(word in message_lower for word in ['не уверен', 'сомневаюсь', 'страшно', 'боюсь', 'не верю', 'подумаю', 'позже']):
            state['stage'] = 'offering_help'  # Возвращаем к предложению
            
            encouragement = [
                f"{user_name}, страх - это нормально\nно он часто скрывает самые важные возможности",
                f"понимаю сомнения\nно что если это именно тот шаг, который нужен тебе сейчас",
                f"{user_name}, доверься своему внутреннему чувству\nоно знает, что для тебя лучше"
            ]
            
            response = get_unique_response(encouragement, state.get('chat_id'), 'encouragement')
            return [format_message(response, False)]
        
        else:
            state['stage'] = 'offering_help'
            return [format_message("хочешь попробовать взглянуть на ситуацию по-новому?", False)]
    
    # По умолчанию возвращаем к проблеме
    state['stage'] = 'problem_received'
    return [format_message("расскажи, что происходит", False)]

def process_user_message(chat_id, user_name, message_text):
    """Обрабатывает сообщение пользователя"""
    state = get_conversation_state(chat_id)
    state['user_name'] = user_name
    
    # Если это первое сообщение и оно похоже на проблему
    if is_first_message(chat_id, message_text) and not user_first_messages[chat_id]['processed']:
        if is_problem_message(message_text):
            # Обрабатываем как проблему сразу
            mark_first_message_processed(chat_id)
            responses = generate_problem_response(message_text, user_name, state)
            return responses
        else:
            # Если не проблема, все равно начинаем диалог
            mark_first_message_processed(chat_id)
            state['greeted'] = True
            return [format_message(f"привет, {user_name}\nрасскажи, что на душе", False)]
    
    # Обычная обработка
    if is_problem_message(message_text) and state['stage'] == 'problem_received':
        # Если прислали проблему на этапе получения проблемы
        responses = generate_problem_response(message_text, user_name, state)
    else:
        # Продолжаем диалог
        responses = generate_followup_response(message_text, user_name, state)
    
    return responses

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной webhook - обрабатывает ВСЕ сообщения, включая /start"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error"}), 400
        
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text'].strip()
            chat_id = data['message']['chat']['id']
            user_name = data['message']['from'].get('first_name', 'друг')
            
            logger.info(f"👤 {user_name}: {message_text}")
            
            # Показываем печать сразу
            show_typing(chat_id)
            
            # Обрабатываем ЛЮБОЕ сообщение, включая /start
            # Если пришло /start - игнорируем команду, начинаем диалог
            if message_text.lower() == '/start':
                # Сбрасываем состояние для нового диалога
                if chat_id in conversations:
                    del conversations[chat_id]
                if chat_id in message_history:
                    del message_history[chat_id]
                if chat_id in user_first_messages:
                    del user_first_messages[chat_id]
                
                # Начинаем диалог с приветствия
                responses = [format_message(f"привет, {user_name} ✨\nрасскажи, что привело тебя сегодня", False)]
            else:
                # Обрабатываем обычное сообщение
                responses = process_user_message(chat_id, user_name, message_text)
            
            # Отправляем ответы
            if responses:
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

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "bot": "@Tarotyour_bot",
        "description": "Бот-таролог, который сразу работает с проблемами",
        "features": [
            "Не требует /start - начинает диалог с первого сообщения",
            "Определяет проблемы автоматически",
            "Уникальные неповторяющиеся ответы",
            "Задержки 1-3 минуты"
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info("🚀 Бот запущен - работает БЕЗ обязательного /start")
    logger.info("🎯 Начинает диалог с первого сообщения пользователя")
    logger.info("⏰ Задержки: 60-180 секунд")
    app.run(host='0.0.0.0', port=port, debug=False)
