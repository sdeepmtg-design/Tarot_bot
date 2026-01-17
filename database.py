import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Простая in-memory база для старта
class SimpleDB:
    def __init__(self):
        self.users = {}
        self.readings = {}
        self.conversations = {}
    
    def save_reading(self, user_id, question, card, interpretation):
        """Сохраняет расклад"""
        try:
            reading_id = f"{user_id}_{datetime.now().timestamp()}"
            self.readings[reading_id] = {
                'user_id': user_id,
                'question': question,
                'card': card,
                'interpretation': interpretation,
                'timestamp': datetime.now().isoformat()
            }
            return reading_id
        except Exception as e:
            logger.error(f"Error saving reading: {e}")
            return None
    
    def get_user_readings(self, user_id, limit=10):
        """Получает расклады пользователя"""
        try:
            user_readings = []
            for reading_id, reading in self.readings.items():
                if reading['user_id'] == user_id:
                    user_readings.append(reading)
            
            # Сортируем по времени (новые сначала)
            user_readings.sort(key=lambda x: x['timestamp'], reverse=True)
            return user_readings[:limit]
        except Exception as e:
            logger.error(f"Error getting readings: {e}")
            return []
    
    def save_conversation(self, user_id, role, content):
        """Сохраняет сообщение в историю"""
        try:
            if user_id not in self.conversations:
                self.conversations[user_id] = []
            
            # Ограничиваем историю до 20 сообщений
            if len(self.conversations[user_id]) >= 20:
                self.conversations[user_id].pop(0)
            
            self.conversations[user_id].append({
                'role': role,
                'content': content,
                'timestamp': datetime.now().isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return False
    
    def get_conversation_history(self, user_id, limit=10):
        """Получает историю разговоров"""
        try:
            if user_id in self.conversations:
                return self.conversations[user_id][-limit:]
            return []
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

# Глобальная база данных
db = SimpleDB()
