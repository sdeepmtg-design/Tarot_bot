from flask import Flask, request, jsonify
import os
import requests
import logging
import random
import time
import threading
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

# Хранилища
conversations = {}
used_responses = {}
typing_status = {}  # Для отслеживания статуса "печатает"

def show_typing(chat_id, duration=None):
    """Показывает статус 'печатает' в чате"""
    if duration is None:
        duration = random.uniform(2.0, 5.0)  # Показываем печать 2-5 секунд
    
    def typing_action():
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction"
            payload = {
                'chat_id': chat_id,
                'action': 'typing'
            }
            response = requests.post(url, json=payload, timeout=5)
            time.sleep(duration)
            return response.status_code == 200
        except Exception:
            return False
    
    thread = threading.Thread(target=typing_action)
    thread.daemon = True
    thread.start()
    return thread

def get_human_delay():
    """Возвращает задержку от 1 до 3 минут (60-180 секунд)"""
    return random.randint(60, 180)  # 1-3 минуты

def send_message_with_human_timing(chat_id, text, is_fast_mode=False):
    """Отправляет сообщение с человеческими задержками и статусом печати"""
    def send_sequence():
        # 1. Показываем "печатает" перед задержкой
        show_typing(chat_id, duration=random.uniform(3.0, 8.0))
        
        # 2. Основная задержка 1-3 минуты
        delay = get_human_delay() if not is_fast_mode else random.randint(30, 90)  # 30-90 сек в быстром режиме
        logger.info(f"⏰ Задержка: {delay} сек перед ответом")
        time.sleep(delay)
        
        # 3. Снова показываем "печатает" перед отправкой
        show_typing(chat_id, duration=random.uniform(1.5, 4.0))
        time.sleep(random.uniform(1.5, 4.0))
        
        # 4. Отправляем сообщение
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Ошибка отправки: {response.text}")
        except Exception as e:
            logger.error(f"Ошибка: {e}")
    
    thread = threading.Thread(target=send_sequence)
    thread.daemon = True
    thread.start()
    return thread

def send_multiple_messages(chat_id, messages, is_fast_mode=False):
    """Отправляет несколько сообщений с паузами и статусом печати"""
    def send_sequence():
        for i, msg in enumerate(messages):
            if i > 0:
                # Пауза между сообщениями с показом печати
                pause = random.randint(10, 30)  # 10-30 сек между сообщениями
                logger.info(f"⏸️ Пауза между сообщениями: {pause} сек")
                time.sleep(pause)
            
            # Показываем печать перед каждым сообщением
            show_typing(chat_id, duration=random.uniform(2.0, 5.0))
            time.sleep(random.uniform(2.0, 5.0))
            
            # Отправляем сообщение
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': msg,
                    'parse_mode': 'Markdown'
                }
                requests.post(url, json=payload, timeout=10)
            except Exception:
                pass
    
    thread = threading.Thread(target=send_sequence)
    thread.daemon = True
    thread.start()
    return thread

def get_unique_response(responses, chat_id, response_type):
    """Возвращает уникальный ответ"""
    if chat_id not in used_responses:
        used_responses[chat_id] = {}
    
    if response_type not in used_responses[chat_id]:
        used_responses[chat_id][response_type] = []
    
    available = [r for r in responses if r not in used_responses[chat_id][response_type]]
    
    if not available:
        used_responses[chat_id][response_type] = []
        available = responses
    
    chosen = random.choice(available)
    used_responses[chat_id][response_type].append(chosen)
    
    if len(used_responses[chat_id][response_type]) > 4:
        used_responses[chat_id][response_type] = used_responses[chat_id][response_type][-4:]
    
    return chosen

def format_naturally(text, is_fast=False):
    """Форматирует текст для естественности"""
    if is_fast and len(text) < 100:
        if random.random() < 0.7:
            text = text[0].lower() + text[1:] if text else text
        
        if random.random() < 0.5 and text.endswith('.'):
            text = text[:-1]
    
    if random.random() < 0.4 and ", что" in text:
        text = text.replace(", что", " что")
    
    if random.random() < 0.15:
        slang = {
            'понимаю': ['понимаю', 'ясно', 'чувствую', 'врубаюсь'][random.randint(0, 3)],
            'конечно': ['конечно', 'разумеется', 'естессно'][random.randint(0, 2)],
            'спасибо': ['спасибо', 'спс', 'благодарю'][random.randint(0, 2)]
        }
        
        for formal, informal in slang.items():
            if formal in text.lower():
                text = text.replace(formal, informal)
                break
    
    return text

def get_conversation_state(chat_id, user_name):
    """Получает состояние диалога"""
    if chat_id not in conversations:
        conversations[chat_id] = {
            'stage': 'greeting',
            'user_name': user_name,
            'problem': '',
            'trust_level': 0,
            'last_interaction': time.time(),
            'message_count': 0,
            'fast_mode': False,
            'payment_offered': False,
            'payment_link_sent': False,
            'waiting_for_payment': False,
            'conversation_start': time.time()
        }
    
    conversations[chat_id]['last_interaction'] = time.time()
    conversations[chat_id]['message_count'] += 1
    
    # Определяем быстрый режим (отвечают быстрее 2 минут)
    current_time = time.time()
    if 'last_message_time' in conversations[chat_id]:
        time_diff = current_time - conversations[chat_id]['last_message_time']
        conversations[chat_id]['fast_mode'] = time_diff < 120  # 2 минуты
    
    conversations[chat_id]['last_message_time'] = current_time
    conversations[chat_id]['user_name'] = user_name  # Обновляем имя
    
    return conversations[chat_id]

def generate_response(user_message, chat_id, user_name):
    """Генерирует ответ на основе диалога"""
    state = get_conversation_state(chat_id, user_name)
    user_msg_lower = user_message.lower()
    stage = state['stage']
    name = state['user_name']
    is_fast = state['fast_mode']
    
    logger.info(f"💬 Стадия: {stage}, Сообщений: {state['message_count']}, Быстрый: {is_fast}")
    
    # Показываем печать сразу при получении сообщения
    show_typing(chat_id)
    
    # 1. ПРИВЕТСТВИЕ
    if stage == 'greeting':
        state['stage'] = 'listening'
        
        greetings = [
            f"привет, {name} ✨\nкак твое настроение сегодня",
            f"здравствуй, {name}\nчувствую, ты пришел не просто так",
            f"о, {name}, приветствую\nчто-то важное на душе",
            f"привет, {name}\nкак дела? что привело тебя сюда",
            f"{name}, здравствуй\nчувствую легкое волнение от тебя"
        ]
        
        response = get_unique_response(greetings, chat_id, 'greeting')
        return [format_naturally(response, is_fast)]
    
    # 2. СЛУШАНИЕ
    elif stage == 'listening':
        if len(user_message) > 10:
            state['problem'] = user_message
            state['stage'] = 'empathy'
            state['trust_level'] += 1
            
            empathy = [
                f"ой, {name}... слышу, как это непросто\nдержи, я с тобой",
                f"понимаю, {name}\nтакое действительно выматывает\n\nне торопись, я слушаю",
                f"мм, да... {name}\nчувствую тяжесть этого\n\nможно дышать глубже, я рядом",
                f"слышу тебя, {name}\nэто важно - делиться таким\n\nспасибо за доверие"
            ]
            
            response1 = get_unique_response(empathy, chat_id, 'empathy')
            
            follow_ups = [
                "расскажи еще, если хочется\nчто в этом самое болезненное",
                "а что твое сердце чувствует в этой ситуации",
                "как долго это с тобой, {name}",
                "что бы хотелось изменить в первую очередь"
            ]
            
            response2 = random.choice(follow_ups).format(name=name)
            
            return [
                format_naturally(response1, is_fast),
                format_naturally(response2, is_fast)
            ]
        else:
            return [format_naturally("расскажи чуть подробнее, если готов\nя действительно слушаю", is_fast)]
    
    # 3. ЭМПАТИЯ
    elif stage == 'empathy':
        state['stage'] = 'wisdom'
        state['trust_level'] += 1
        
        wisdom = [
            f"интересно, {name}...\nа если бы страх отпустил\nчто бы ты сделал первым делом",
            f"знаешь, {name}\nиногда такие ситуации - как зеркало\n\nчто это зеркало показывает тебе",
            f"чувствую, {name}\nздесь есть что-то важное для твоего пути\n\nчто это может быть",
            f"{name}, а что если это не проблема\nа возможность увидеть что-то новое в себе"
        ]
        
        response = get_unique_response(wisdom, chat_id, 'wisdom')
        return [format_naturally(response, is_fast)]
    
    # 4. МУДРОСТЬ
    elif stage == 'wisdom':
        state['stage'] = 'offering_help'
        
        offering = [
            f"{name}, иногда нам нужен другой взгляд\nчтобы увидеть то, что скрыто\n\nкарты таро могут стать таким проводником",
            f"знаешь, я часто вижу\nкак карты помогают найти ответы внутри себя\n\nхочешь попробовать такой диалог",
            f"{name}, у меня есть чувство\nчто здесь есть важные подсказки для тебя\n\nкарты могут помочь их расшифровать",
            f"иногда полезно посмотреть на ситуацию\nчерез призму символов и образов\n\n{name}, интересно тебе такое исследование"
        ]
        
        response1 = get_unique_response(offering, chat_id, 'offering')
        response2 = "это не гадание, а разговор с собой\nчерез язык карт и интуиции"
        
        return [
            format_naturally(response1, is_fast),
            format_naturally(response2, is_fast)
        ]
    
    # 5. ПРЕДЛОЖЕНИЕ ПОМОЩИ
    elif stage == 'offering_help':
        positive = ['да', 'хочу', 'готов', 'соглас', 'интересно', 'можно', 'попробую', 'почему нет', 'давай', 'расскажи']
        
        if any(word in user_msg_lower for word in positive):
            state['stage'] = 'discussing_value'
            state['payment_offered'] = True
            
            value = [
                f"хорошо, {name} 💫\nтогда я создам для тебя персональный расклад",
                "буду работать с твоей ситуацией очень внимательно",
                f"стоимость - 1490 рублей\nно для тебя, {name}, сделаю за 990",
                "это не просто оплата\nа энергообмен и твоя готовность к изменениям"
            ]
            
            return [format_naturally(r, is_fast) for r in value]
        else:
            comfort = [
                f"всё в твоем ритме, {name}\nне торопись с решением",
                f"посиди с этим ощущением, {name}\nоно тебе что-то говорит",
                f"как думаешь, {name}\nчего не хватает для принятия решения"
            ]
            
            response = get_unique_response(comfort, chat_id, 'comfort')
            return [format_naturally(response, is_fast)]
    
    # 6. ОБСУЖДЕНИЕ ЦЕННОСТИ
    elif stage == 'discussing_value':
        if 'сколько' in user_msg_lower or 'цена' in user_msg_lower or 'стоимость' in user_msg_lower or '990' in user_msg_lower:
            state['stage'] = 'asking_readiness'
            
            readiness = [
                f"{name}, как тебе такая инвестиция в себя\n990 рублей за ясность и новые перспективы",
                f"чувствую, это доступная сумма для важного шага\n{name}, ты так не считаешь",
                f"{name}, это меньше, чем многие тратят на то, что не приносит счастья\nа здесь - инвестиция в твой покой"
            ]
            
            response = get_unique_response(readiness, chat_id, 'readiness')
            return [format_naturally(response, is_fast)]
        
        elif 'готов' in user_msg_lower or 'куплю' in user_msg_lower or 'оплат' in user_msg_lower:
            state['stage'] = 'sending_link'
            
            pre_link = [
                f"чувствую твою решимость, {name} ✨\nэто вдохновляет",
                "момент выбора всегда особенный",
                f"{name}, сейчас произойдет что-то важное\nмежду нами и для тебя"
            ]
            
            return [format_naturally(r, is_fast) for r in pre_link]
        
        else:
            state['stage'] = 'asking_readiness'
            return [format_naturally(f"{name}, готов сделать этот шаг к ясности", is_fast)]
    
    # 7. ПРОВЕРКА ГОТОВНОСТИ
    elif stage == 'asking_readiness':
        if any(word in user_msg_lower for word in ['готов', 'давай', 'хочу', 'куплю', 'оплат']):
            state['stage'] = 'sending_link'
            state['waiting_for_payment'] = True
            
            confirm = [
                f"отлично, {name} 🌟",
                "чувствую, как энергия двигается",
                "этот шаг изменит многое для тебя"
            ]
            
            return [format_naturally(r, is_fast) for r in confirm]
        
        else:
            return [format_naturally(f"{name}, всё в твоем темпе\nпросто скажи, когда будешь готов", is_fast)]
    
    # 8. ОТПРАВКА ССЫЛКИ
    elif stage == 'sending_link' and not state['payment_link_sent']:
        state['payment_link_sent'] = True
        state['stage'] = 'awaiting_payment'
        
        # Важно: сначала предварительное сообщение, потом ссылка
        payment_url = "https://yoomoney.ru/to/4100111234567890"  # ЗАМЕНИТЕ!
        
        return [
            "держи ссылку для оплаты",
            payment_url
        ]
    
    # 9. ОЖИДАНИЕ ОПЛАТЫ
    elif stage == 'awaiting_payment':
        if 'оплат' in user_msg_lower or 'перевел' in user_msg_lower or 'сделал' in user_msg_lower or 'оплатил' in user_msg_lower:
            state['stage'] = 'working'
            state['waiting_for_payment'] = False
            
            gratitude = [
                f"благодарю, {name} 🙏\nэнергия пошла",
                "чувствую твое доверие\nэто ценно",
                "начинаю работать с картами\nдля твоего расклада",
                "займет немного времени\nно оно того стоит\n\nотдохни, скоро вернусь с ответами"
            ]
            
            return [format_naturally(r, is_fast) for r in gratitude]
        
        elif not state['payment_link_sent']:
            state['stage'] = 'sending_link'
            return ["дай секунду, пришлю ссылку"]
        
        else:
            reminders = [
                f"я здесь, {name}\nжду, когда будешь готов",
                "всё в твоем ритме\nссылка ждет тебя",
                f"{name}, помни - это шаг к ясности\nкогда захочешь - оплати"
            ]
            
            response = get_unique_response(reminders, chat_id, 'reminders')
            return [format_naturally(response, is_fast)]
    
    # 10. РАБОТА
    elif stage == 'working':
        updates = [
            "карты уже говорят...\nчто-то важное про твой путь",
            "вижу интересные связи\nто, что было скрыто",
            f"{name}, это глубже, чем кажется\nи прекраснее тоже",
            "почти готово\nсобираю для тебя ответы\nв целостную картину"
        ]
        
        response = get_unique_response(updates, chat_id, 'updates')
        return [format_naturally(response, is_fast)]
    
    # Запасной
    state['stage'] = 'listening'
    return [format_naturally(f"{name}, расскажи, что на душе прямо сейчас", is_fast)]

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
            
            logger.info(f"👤 {user_name}: {message_text}")
            
            # Показываем "печатает" сразу
            show_typing(chat_id)
            
            # Обработка /start
            if message_text.lower() == '/start':
                if chat_id in conversations:
                    del conversations[chat_id]
                if chat_id in used_responses:
                    del used_responses[chat_id]
            
            # Генерируем ответ
            responses = generate_response(message_text, chat_id, user_name)
            
            # Отправляем с человеческими задержками
            if responses:
                if len(responses) == 1:
                    send_message_with_human_timing(chat_id, responses[0], 
                        conversations.get(chat_id, {}).get('fast_mode', False))
                else:
                    send_multiple_messages(chat_id, responses, 
                        conversations.get(chat_id, {}).get('fast_mode', False))
            
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

@app.route('/stats', methods=['GET'])
def stats():
    """Статистика бота"""
    active_chats = len(conversations)
    total_messages = sum(state.get('message_count', 0) for state in conversations.values())
    
    return jsonify({
        "status": "active",
        "bot": "@Tarotyour_bot",
        "description": "Эмпатичный проводник с задержками 1-3 минуты",
        "active_chats": active_chats,
        "total_messages": total_messages,
        "features": [
            "Задержки 60-180 секунд",
            "Индикатор 'печатает'",
            "Уникальные неповторяющиеся ответы",
            "Четкая воронка до оплаты"
        ],
        "timing": {
            "min_delay": "60 сек (1 минута)",
            "max_delay": "180 сек (3 минуты)",
            "typing_indicator": "включен",
            "fast_mode_threshold": "120 сек (2 минуты)"
        }
    })

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "bot": "@Tarotyour_bot",
        "message": "Бот работает с задержками 1-3 минуты и показывает статус 'печатает'"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Запуск бота с задержками 1-3 минуты на порту {port}")
    logger.info("⏰ Задержки: 60-180 секунд")
    logger.info("⌨️ Индикатор 'печатает': включен")
    app.run(host='0.0.0.0', port=port, debug=False)
