from flask import Flask, request, jsonify
import os
import requests
import logging
import random
import time
import threading

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

# Состояния диалогов
dialog_states = {}

def send_human_message(chat_id, text, parse_mode='Markdown', delay=None):
    """Отправляет сообщение как человек - с задержкой и естественностью"""
    if delay is None:
        # Чем короче ответ - тем быстрее отвечаем
        if len(text) < 80:
            delay = random.uniform(0.8, 2.5)  # 0.8-2.5 сек для коротких
        else:
            delay = random.uniform(1.5, 4.0)  # 1.5-4 сек для длинных
    
    def send():
        time.sleep(delay)
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.json() if response.status_code == 200 else None
        except Exception:
            return None
    
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()
    return thread

def send_multiple_messages(chat_id, messages, delays=None):
    """Отправляет несколько сообщений с паузами"""
    if not delays:
        delays = [random.uniform(1.2, 3.0) for _ in messages]
    
    for i, msg in enumerate(messages):
        time.sleep(delays[i] if i > 0 else 0)
        send_human_message(chat_id, msg, delay=0)

def get_dialog_state(chat_id):
    if chat_id not in dialog_states:
        dialog_states[chat_id] = {
            'stage': 'greeting',
            'problem': '',
            'emotions': [],
            'trust_level': 0,
            'last_msg_time': time.time(),
            'msg_count': 0,
            'fast_mode': False,
            'user_name': ''
        }
    return dialog_states[chat_id]

def update_stage(chat_id, stage):
    dialog_states[chat_id]['stage'] = stage
    dialog_states[chat_id]['last_msg_time'] = time.time()

def format_message(text, fast_mode=False):
    """Форматирует текст для естественности"""
    if fast_mode and len(text.split()) < 15:
        # Для быстрой переписки - с маленькой буквы
        text = text[0].lower() + text[1:]
    
    # Иногда убираем запятую перед "что"
    if random.random() < 0.3 and ", что" in text:
        text = text.replace(", что", " что")
    
    # В конце предложения не всегда ставим точку
    if random.random() < 0.4 and text.endswith('.'):
        text = text[:-1]
    
    # Добавляем немного сленга для близости
    slang_replacements = {
        'понимаю': ['понимаю', 'ясно', 'врубаюсь', 'улавливаю'][random.randint(0, 3)],
        'спасибо': ['спасибо', 'спс', 'благодарю'][random.randint(0, 2)],
        'конечно': ['конечно', 'естественно', 'разумеется'][random.randint(0, 2)],
        'правильно': ['правильно', 'верно', 'точно'][random.randint(0, 2)],
    }
    
    for formal, informal in slang_replacements.items():
        if random.random() < 0.2 and formal in text.lower():
            text = text.replace(formal, informal)
    
    return text

def generate_empathic_response(user_msg, user_name, state):
    """Генерирует эмпатичный ответ как мудрый знакомый"""
    user_msg_lower = user_msg.lower()
    stage = state['stage']
    state['msg_count'] += 1
    
    # Определяем темп общения
    time_since_last = time.time() - state['last_msg_time']
    state['fast_mode'] = time_since_last < 30  # Быстрый диалог если отвечают быстро
    
    # Запоминаем имя
    if not state['user_name']:
        state['user_name'] = user_name
    
    name = state['user_name']
    
    # Стадия 1: Приветствие и установление контакта
    if stage == 'greeting':
        update_stage(state.get('chat_id'), 'listening')
        
        greetings = [
            f"привет, {name} ✨\nкак дела? что привело ко мне сегодня",
            f"здравствуй, {name}\nчувствую, тебе нужна поддержка... расскажешь, что на душе",
            f"о, {name}, приветствую\nчто-то важное случилось? чувствую энергию запроса"
        ]
        return format_message(random.choice(greetings), state['fast_mode'])
    
    # Стадия 2: Слушание и эмпатия
    elif stage == 'listening':
        if len(user_msg) > 15:  # Пользователь поделился проблемой
            state['problem'] = user_msg
            update_stage(state.get('chat_id'), 'understanding')
            
            # Эмпатичные ответы на проблему
            empath_responses = [
                f"ой, {name}... чувствую, как это тяжело\n\nдержи, я рядом",
                f"понимаю, {name}\nэто действительно непросто...\n\nдыши глубже, я слушаю",
                f"мм, да... {name}\nтакое бывает, когда душа просит перемен\n\nрасскажи еще, если хочешь"
            ]
            
            # Отправляем несколько сообщений для теплоты
            responses = [
                format_message(random.choice(empath_responses), state['fast_mode']),
                "не торопись\nя здесь, чтобы помочь разобраться\n\nчто в этом самое болезненное для тебя?"
            ]
            return responses
        
        else:
            return format_message("расскажи чуть подробнее, если не сложно\nя внимательно слушаю", state['fast_mode'])
    
    # Стадия 3: Глубокое понимание
    elif stage == 'understanding':
        update_stage(state.get('chat_id'), 'wisdom')
        state['trust_level'] += 1
        
        wise_questions = [
            f"а что твое сердце подсказывает, {name}?\nчасто ответ уже есть внутри",
            f"интересно... а если бы не было страха\nкакое решение пришло бы первым",
            f"знаешь, {name}\nиногда ситуации приходят как учителя\n\nчему эта учит тебя?"
        ]
        
        responses = [
            format_message(random.choice(wise_questions), state['fast_mode']),
            "не спеши отвечать\nпросто почувствуй"
        ]
        return responses
    
    # Стадия 4: Мудрость и предложение помощи
    elif stage == 'wisdom':
        update_stage(state.get('chat_id'), 'offering')
        
        wisdom_shares = [
            f"{name}, иногда нужно посмотреть на ситуацию с другой стороны\n\nкарты таро могут стать таким зеркалом",
            f"знаешь, я часто вижу\nкак карты показывают то, что мы не замечаем в суете\n\nхочешь попробовать взглянуть по-новому",
            f"{name}, у меня есть чувство\nчто здесь спрятана важная возможность для роста\n\nкарты помогут её увидеть"
        ]
        
        responses = [
            format_message(random.choice(wisdom_shares), state['fast_mode']),
            "не как гадание, а как разговор с собой\nчерез символы и образы",
            f"если хочешь - могу сделать для тебя расклад\n\n{name}, готов исследовать эту ситуацию глубже?"
        ]
        return responses
    
    # Стадия 5: Предложение расклада
    elif stage == 'offering':
        # Пользователь соглашается или интересуется
        agreement_words = ['да', 'хочу', 'готов', 'соглас', 'интересно', 'можно', 'попробую', 'почему нет', 'давай']
        
        if any(word in user_msg_lower for word in agreement_words):
            update_stage(state.get('chat_id'), 'payment_talk')
            
            gentle_offer = [
                f"отлично, {name} 💫\nтогда я сделаю для тебя особый расклад",
                "буду работать с твоим запросом очень бережно",
                f"стоимость - 1490 рублей\nно для тебя, {name}, сделаю за 990\n\nэто инвестиция в твою ясность"
            ]
            return gentle_offer
        
        else:
            # Если ещё сомневается
            comforting = [
                f"не дави себя, {name}\nрешение должно прийти изнутри",
                "посиди с этим чувством\nоно тебе что-то важное говорит",
                f"как думаешь, {name}\nчего тебе действительно не хватает для принятия решения"
            ]
            return [format_message(random.choice(comforting), state['fast_mode'])]
    
    # Стадия 6: Разговор об оплате с эмпатией
    elif stage == 'payment_talk':
        if 'сколько' in user_msg_lower or 'цена' in user_msg_lower or 'стоимость' in user_msg_lower:
            update_stage(state.get('chat_id'), 'payment_link')
            
            value_explanation = [
                f"{name}, это не просто плата за карты\nэто энергообмен",
                "так устанавливается наша связь\nи твоя серьезность намерения",
                f"я вкладываю в каждый расклад час глубокой работы\nи всю свою чувствительность",
                "990 рублей - это доступно для важного шага к себе\nне находишь?"
            ]
            return value_explanation
        
        elif 'оплат' in user_msg_lower or 'купить' in user_msg_lower or 'заказ' in user_msg_lower:
            update_stage(state.get('chat_id'), 'payment_link')
            
            payment_approach = [
                f"{name}, спасибо за доверие\nэто ценно для меня",
                "когда будешь готов - просто дай знать\nи я пришлю ссылку для оплаты",
                "не как в магазине\nа как между людьми, которые доверяют друг другу"
            ]
            return payment_approach
        
        elif 'готов' in user_msg_lower or 'давай' in user_msg_lower or 'куплю' in user_msg_lower:
            update_stage(state.get('chat_id'), 'sending_link')
            
            pre_link_warmth = [
                f"чувствую твою решимость, {name} ✨\nэто прекрасно",
                "момент выбора всегда вдохновляет",
                "сейчас произойдет что-то важное\nмежду нами и для тебя"
            ]
            return pre_link_warmth
    
    # Стадия 7: Отправка ссылки (только ссылка!)
    elif stage == 'sending_link':
        update_stage(state.get('chat_id'), 'awaiting_payment')
        
        # ТОЛЬКО ССЫЛКА, ничего лишнего
        payment_url = "https://yoomoney.ru/to/4100111234567890"  # ЗАМЕНИТЕ!
        return [payment_url]
    
    # Стадия 8: Ожидание оплаты
    elif stage == 'awaiting_payment':
        if 'оплат' in user_msg_lower or 'перевел' in user_msg_lower or 'сделал' in user_msg_lower:
            update_stage(state.get('chat_id'), 'working')
            
            gratitude_and_work = [
                f"благодарю, {name} 🙏\nэнергия пошла",
                "чувствую твое доверие\nэто многое значит",
                "начинаю работать с картами\nдля твоего расклада",
                "займет немного времени\nно оно того стоит\n\nотдохни, я скоро вернусь с ответами"
            ]
            return gratitude_and_work
        
        else:
            # Мягкое напоминание
            reminders = [
                f"я здесь, {name}\nжду, когда будешь готов",
                "всё в твоем ритме\nне торопись",
                f"ссылка для оплаты:\nhttps://yoomoney.ru/to/4100111234567890\n\n{name}, я верю в твой выбор"
            ]
            return [format_message(random.choice(reminders), state['fast_mode'])]
    
    # Стадия 9: Работа над раскладом
    elif stage == 'working':
        # Симуляция процесса работы
        process_updates = [
            "карты уже говорят...\nчто-то важное про твой путь",
            "вижу интересные связи\nто, что было скрыто",
            f"{name}, это глубже, чем кажется\nи прекраснее тоже",
            "почти готово\nсобираю для тебя ответы\nв целостную картину"
        ]
        return [format_message(random.choice(process_updates), state['fast_mode'])]
    
    # Запасной ответ
    return format_message("чувствую тебя, просто будь здесь и сейчас\nвсё идет как надо", state['fast_mode'])

@app.route('/webhook', methods=['POST'])
def webhook():
    """Основной webhook"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error"}), 400
        
        if 'message' in data and 'text' in data['message']:
            message_text = data['message']['text'].strip()
            chat_id = data['message']['chat']['id']
            user_name = data['message']['from'].get('first_name', 'друг')
            
            logger.info(f"{user_name}: {message_text}")
            
            # Получаем состояние
            state = get_dialog_state(chat_id)
            state['chat_id'] = chat_id
            
            # Обработка /start
            if message_text.lower().startswith('/start'):
                dialog_states[chat_id] = {
                    'stage': 'greeting',
                    'problem': '',
                    'emotions': [],
                    'trust_level': 0,
                    'last_msg_time': time.time(),
                    'msg_count': 0,
                    'fast_mode': False,
                    'user_name': user_name,
                    'chat_id': chat_id
                }
                state = dialog_states[chat_id]
            
            # Генерируем ответ
            response = generate_empathic_response(message_text, user_name, state)
            
            # Отправляем ответ(ы)
            if isinstance(response, list):
                send_multiple_messages(chat_id, response)
            else:
                send_human_message(chat_id, response)
            
            # Обновляем время последнего сообщения
            state['last_msg_time'] = time.time()
            
            return jsonify({"status": "success"}), 200
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"ошибка: {e}")
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
        "persona": "эмпатичный мудрый проводник",
        "style": "человеческое общение, теплые короткие сообщения",
        "note": "бот отвечает как мудрый знакомый, с задержками и эмпатией"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"запускаю эмпатичного бота на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
