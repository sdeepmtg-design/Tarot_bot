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

# Хранилище диалогов с улучшенной структурой
conversations = {}
used_responses = {}  # Чтобы не повторяться

def get_delay_based_on_length(text_length, is_fast_mode=False):
    """Рассчитывает задержку на основе длины текста и режима общения"""
    if is_fast_mode:
        # Быстрый режим: быстрые ответы
        base_delay = random.uniform(1.5, 3.5)
    else:
        # Нормальный режим: задержки как у человека
        if text_length < 50:
            base_delay = random.uniform(2.5, 5.0)  # 2.5-5 сек для коротких
        elif text_length < 150:
            base_delay = random.uniform(3.0, 7.0)  # 3-7 сек для средних
        else:
            base_delay = random.uniform(4.0, 9.0)  # 4-9 сек для длинных
    
    # Добавляем небольшую случайность
    return base_delay * random.uniform(0.8, 1.2)

def send_message_with_delay(chat_id, text, delay_override=None):
    """Отправляет сообщение с человеческой задержкой"""
    def send():
        if delay_override:
            delay = delay_override
        else:
            delay = get_delay_based_on_length(len(text), 
                    conversations.get(chat_id, {}).get('fast_mode', False))
        
        logger.info(f"⏰ Задержка: {delay:.1f} сек для сообщения: {text[:50]}...")
        time.sleep(delay)
        
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            return None
    
    thread = threading.Thread(target=send)
    thread.daemon = True
    thread.start()
    return thread

def send_multiple_with_pauses(chat_id, messages):
    """Отправляет несколько сообщений с паузами между ними"""
    def send_sequence():
        for i, msg in enumerate(messages):
            if i > 0:
                # Пауза между сообщениями 1-3 секунды
                pause = random.uniform(1.0, 3.0)
                time.sleep(pause)
            
            send_message_with_delay(chat_id, msg, delay_override=0.1)  # Быстро отправляем после паузы
    
    thread = threading.Thread(target=send_sequence)
    thread.daemon = True
    thread.start()

def get_unique_response(responses, chat_id, response_type):
    """Возвращает уникальный ответ, который еще не использовался"""
    if chat_id not in used_responses:
        used_responses[chat_id] = {}
    
    if response_type not in used_responses[chat_id]:
        used_responses[chat_id][response_type] = []
    
    available = [r for r in responses if r not in used_responses[chat_id][response_type]]
    
    if not available:
        # Если все использовались, сбрасываем для этого типа
        used_responses[chat_id][response_type] = []
        available = responses
    
    chosen = random.choice(available)
    used_responses[chat_id][response_type].append(chosen)
    
    # Ограничиваем историю 5 последними ответами каждого типа
    if len(used_responses[chat_id][response_type]) > 5:
        used_responses[chat_id][response_type] = used_responses[chat_id][response_type][-5:]
    
    return chosen

def format_naturally(text, is_fast=False):
    """Форматирует текст для естественности"""
    if is_fast and len(text) < 100:
        # Для быстрой переписки - более неформально
        if random.random() < 0.6:
            text = text[0].lower() + text[1:] if text else text
        
        if random.random() < 0.4 and text.endswith('.'):
            text = text[:-1]
    
    # Случайно убираем запятую перед "что"
    if random.random() < 0.3 and ", что" in text:
        text = text.replace(", что", " что")
    
    # Добавляем немного естественных "сбоев"
    if random.random() < 0.1:
        replacements = {
            'понимаю': ['понимаю', 'ясно', 'чувствую'][random.randint(0, 2)],
            'конечно': ['конечно', 'разумеется', 'естессно'][random.randint(0, 2)],
            'спасибо': ['спасибо', 'спс', 'благодарю'][random.randint(0, 2)]
        }
        
        for formal, informal in replacements.items():
            if formal in text.lower():
                text = text.replace(formal, informal)
                break
    
    return text

def get_conversation_state(chat_id, user_name):
    """Получает или создает состояние диалога"""
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
            'unique_id': f"{chat_id}_{int(time.time())}",
            'waiting_for_payment': False,
            'last_responses': {}
        }
    
    # Обновляем время последнего взаимодействия
    conversations[chat_id]['last_interaction'] = time.time()
    conversations[chat_id]['message_count'] += 1
    
    # Определяем режим скорости
    current_time = time.time()
    if 'last_message_time' in conversations[chat_id]:
        time_diff = current_time - conversations[chat_id]['last_message_time']
        conversations[chat_id]['fast_mode'] = time_diff < 45  # Если отвечают быстрее 45 сек
    conversations[chat_id]['last_message_time'] = current_time
    
    return conversations[chat_id]

def generate_response(user_message, chat_id, user_name):
    """Генерирует ответ на основе диалога"""
    state = get_conversation_state(chat_id, user_name)
    user_msg_lower = user_message.lower()
    stage = state['stage']
    name = state['user_name']
    is_fast = state['fast_mode']
    
    logger.info(f"💬 Стадия: {stage}, Быстрый режим: {is_fast}")
    
    # 📍 1. ПРИВЕТСТВИЕ
    if stage == 'greeting':
        state['stage'] = 'listening'
        
        greetings = [
            f"привет, {name} ✨\nкак твое настроение сегодня?",
            f"здравствуй, {name}\nчувствую, ты пришел не просто так...",
            f"о, {name}, приветствую\nчто-то важное на душе?",
            f"привет, {name}\nкак дела? что привело тебя сюда",
            f"{name}, здравствуй\nчувствую легкое волнение от тебя..."
        ]
        
        response = get_unique_response(greetings, chat_id, 'greeting')
        return [format_naturally(response, is_fast)]
    
    # 📍 2. СЛУШАНИЕ ПРОБЛЕМЫ
    elif stage == 'listening':
        if len(user_message) > 10:  # Пользователь поделился
            state['problem'] = user_message
            state['stage'] = 'empathy'
            state['trust_level'] += 1
            
            empathy_responses = [
                f"ой, {name}... слышу, как это непросто\nдержи, я с тобой",
                f"понимаю, {name}\nтакое действительно выматывает...\n\nне торопись, я слушаю",
                f"мм, да... {name}\nчувствую тяжесть этого\n\nможно дышать глубже, я рядом",
                f"слышу тебя, {name}\nэто важно - делиться таким\n\nспасибо за доверие",
                f"{name}... да, такое бывает\nкогда все накапливается\n\nты не одинок в этом"
            ]
            
            response1 = get_unique_response(empathy_responses, chat_id, 'empathy')
            
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
    
    # 📍 3. ЭМПАТИЯ И ПОНИМАНИЕ
    elif stage == 'empathy':
        state['stage'] = 'wisdom'
        state['trust_level'] += 1
        
        wisdom_responses = [
            f"интересно, {name}...\nа если бы страх отпустил\nчто бы ты сделал первым делом",
            f"знаешь, {name}\nиногда такие ситуации - как зеркало\n\nчто это зеркало показывает тебе",
            f"чувствую, {name}\nздесь есть что-то важное для твоего пути\n\nчто это может быть",
            f"{name}, а что если это не проблема\nа возможность увидеть что-то новое в себе",
            f"понимаю... {name}\nа что поддерживает тебя в такие моменты"
        ]
        
        response = get_unique_response(wisdom_responses, chat_id, 'wisdom')
        return [format_naturally(response, is_fast)]
    
    # 📍 4. МУДРОСТЬ И ПРЕДЛОЖЕНИЕ ПОМОЩИ
    elif stage == 'wisdom':
        state['stage'] = 'offering_help'
        
        offering_responses = [
            f"{name}, иногда нам нужен другой взгляд\nчтобы увидеть то, что скрыто\n\nкарты таро могут стать таким проводником",
            f"знаешь, я часто вижу\nкак карты помогают найти ответы внутри себя\n\nхочешь попробовать такой диалог",
            f"{name}, у меня есть чувство\nчто здесь есть важные подсказки для тебя\n\nкарты могут помочь их расшифровать",
            f"иногда полезно посмотреть на ситуацию\nчерез призму символов и образов\n\n{name}, интересно тебе такое исследование"
        ]
        
        response1 = get_unique_response(offering_responses, chat_id, 'offering')
        
        response2 = "это не гадание, а разговор с собой\nчерез язык карт и интуиции"
        
        return [
            format_naturally(response1, is_fast),
            format_naturally(response2, is_fast)
        ]
    
    # 📍 5. ПРЕДЛОЖЕНИЕ РАСКЛАДА
    elif stage == 'offering_help':
        # Проверяем интерес пользователя
        positive_words = ['да', 'хочу', 'готов', 'соглас', 'интересно', 'можно', 'попробую', 'почему нет', 'давай', 'расскажи']
        
        if any(word in user_msg_lower for word in positive_words):
            state['stage'] = 'discussing_value'
            state['payment_offered'] = True
            
            value_responses = [
                f"хорошо, {name} 💫\nтогда я создам для тебя персональный расклад",
                "буду работать с твоей ситуацией очень внимательно",
                f"стоимость - 1490 рублей\nно для тебя, {name}, сделаю за 990",
                "это не просто оплата\nа энергообмен и твоя готовность к изменениям"
            ]
            
            return [format_naturally(r, is_fast) for r in value_responses]
        
        else:
            # Если ещё не готов
            comforting = [
                f"всё в твоем ритме, {name}\nне торопись с решением",
                f"посиди с этим ощущением, {name}\nоно тебе что-то говорит",
                f"как думаешь, {name}\nчего не хватает для принятия решения"
            ]
            
            response = get_unique_response(comforting, chat_id, 'comforting')
            return [format_naturally(response, is_fast)]
    
    # 📍 6. ОБСУЖДЕНИЕ ЦЕННОСТИ
    elif stage == 'discussing_value':
        if 'сколько' in user_msg_lower or 'цена' in user_msg_lower or 'стоимость' in user_msg_lower or '990' in user_msg_lower:
            state['stage'] = 'asking_readiness'
            
            readiness_questions = [
                f"{name}, как тебе такая инвестиция в себя\n990 рублей за ясность и новые перспективы",
                f"чувствую, это доступная сумма для важного шага\n{name}, ты так не считаешь",
                f"{name}, это меньше, чем многие тратят на то, что не приносит счастья\nа здесь - инвестиция в твой покой"
            ]
            
            response = get_unique_response(readiness_questions, chat_id, 'readiness')
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
            return [format_naturally(f"{name}, готов сделать этот шаг к ясности?", is_fast)]
    
    # 📍 7. СПРАШИВАЕМ О ГОТОВНОСТИ
    elif stage == 'asking_readiness':
        if any(word in user_msg_lower for word in ['готов', 'давай', 'хочу', 'куплю', 'оплат']):
            state['stage'] = 'sending_link'
            state['waiting_for_payment'] = True
            
            confirmation = [
                f"отлично, {name} 🌟",
                "чувствую, как энергия двигается",
                "этот шаг изменит многое для тебя"
            ]
            
            return [format_naturally(r, is_fast) for r in confirmation]
        
        else:
            return [format_naturally(f"{name}, всё в твоем темпе\nпросто скажи, когда будешь готов", is_fast)]
    
    # 📍 8. ОТПРАВКА ССЫЛКИ (ВАЖНО: ТОЛЬКО ССЫЛКА!)
    elif stage == 'sending_link' and not state['payment_link_sent']:
        state['payment_link_sent'] = True
        state['stage'] = 'awaiting_payment'
        
        # ТОЛЬКО ССЫЛКА, без лишних слов
        payment_url = "https://yoomoney.ru/to/4100111234567890"  # ЗАМЕНИТЕ НА РЕАЛЬНУЮ
        
        # Сначала отправляем подготовительное сообщение
        # Затем через паузу - ссылку
        return [
            "держи ссылку для оплаты",
            payment_url
        ]
    
    # 📍 9. ОЖИДАНИЕ ОПЛАТЫ
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
            # Если вдруг ссылка не отправилась
            state['stage'] = 'sending_link'
            return ["дай секунду, пришлю ссылку"]
        
        else:
            # Мягкое напоминание
            reminders = [
                f"я здесь, {name}\nжду, когда будешь готов",
                "всё в твоем ритме\nссылка ждет тебя",
                f"{name}, помни - это шаг к ясности\nкогда захочешь - оплати"
            ]
            
            response = get_unique_response(reminders, chat_id, 'reminders')
            return [format_naturally(response, is_fast)]
    
    # 📍 10. РАБОТА НАД РАСКЛАДОМ
    elif stage == 'working':
        process_updates = [
            "карты уже говорят...\nчто-то важное про твой путь",
            "вижу интересные связи\nто, что было скрыто",
            f"{name}, это глубже, чем кажется\nи прекраснее тоже",
            "почти готово\nсобираю для тебя ответы\nв целостную картину"
        ]
        
        response = get_unique_response(process_updates, chat_id, 'updates')
        return [format_naturally(response, is_fast)]
    
    # 📍 Запасной ответ
    state['stage'] = 'listening'  # Возвращаем к слушанию
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
            
            # Обработка /start
            if message_text.lower() == '/start':
                # Сбрасываем состояние для нового диалога
                if chat_id in conversations:
                    del conversations[chat_id]
                if chat_id in used_responses:
                    del used_responses[chat_id]
            
            # Генерируем ответ
            responses = generate_response(message_text, chat_id, user_name)
            
            # Отправляем ответы с задержками
            if responses:
                if len(responses) == 1:
                    send_message_with_delay(chat_id, responses[0])
                else:
                    send_multiple_with_pauses(chat_id, responses)
            
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
        "description": "Эмпатичный проводник с задержками и уникальными ответами",
        "features": [
            "Задержки 2-9 секунд",
            "Уникальные неповторяющиеся ответы",
            "Четкая воронка до оплаты",
            "Только ссылка без лишних слов"
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Запуск бота с задержками и уникальными ответами на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
