import random
from datetime import datetime
from typing import List, Dict

class TarotUtils:
    @staticmethod
    def format_spread_for_display(cards: List[Dict], spread_type: str) -> str:
        spread_info = {
            "past_present_future": ["📜 Прошлое", "🌀 Настоящее", "✨ Будущее"],
            "celtic_cross": ["1️⃣ Сердце", "2️⃣ Препятствие", "3️⃣ Цели", "4️⃣ Бессознательное", 
                           "5️⃣ Прошлое", "6️⃣ Будущее", "7️⃣ Отношение", "8️⃣ Влияния", 
                           "9️⃣ Надежды", "🔟 Итог"],
            "relationship": ["❤️ Ваши чувства", "💙 Чувства партнера", "💞 Динамика", 
                           "🚧 Препятствия", "🌱 Потенциал"],
            "career": ["💼 Ситуация", "🧱 Препятствия", "🎯 Возможности", "💡 Рекомендации"],
            "yes_no": ["⚡ Ответ"]
        }
        
        positions = spread_info.get(spread_type, [f"{i+1}." for i in range(len(cards))])
        
        result = "🃏 *Карты расклада:*\n\n"
        for pos, card in zip(positions, cards):
            result += f"{pos}\n"
            result += f"*{card['name']}*\n"
            if card['reversed']:
                result += "🔄 *Перевернута*\n"
            result += f"_{card['meaning']}_\n\n"
        
        return result
    
    @staticmethod
    def generate_ritual_text() -> str:
        rituals = [
            "🌀 Зажигаю виртуальные свечи... Настраиваюсь на твою энергию...",
            "🌙 Очищаю пространство кристаллами... Перемешиваю карты...",
            "✨ Создаю священное пространство... Карты начинают говорить..."
        ]
        return random.choice(rituals)
    
    @staticmethod
    def moon_phase_emoji() -> str:
        day = datetime.now().day
        if day <= 7:
            return "🌑"
        elif day <= 14:
            return "🌓"
        elif day <= 21:
            return "🌕"
        else:
            return "🌗"

class SubscriptionPlans:
    PLANS = {
        "week": {
            "name": "Неделя",
            "price": 299,
            "days": 7,
            "features": [
                "✅ Все расклады до 5 карт",
                "✅ Ежедневные инсайты",
                "✅ История раскладов"
            ]
        },
        "month": {
            "name": "Месяц",
            "price": 999,
            "days": 30,
            "features": [
                "✅ ВСЕ расклады",
                "✅ Персонализированные инсайты",
                "✅ Расширенная история",
                "✅ Личный дневник карт"
            ]
        }
    }
    
    @classmethod
    def get_plan_info(cls, plan_type: str) -> Dict:
        return cls.PLANS.get(plan_type, {})
    
    @classmethod
    def format_plan_for_display(cls, plan_type: str) -> str:
        plan = cls.get_plan_info(plan_type)
        if not plan:
            return ""
        
        text = f"""💫 *{plan['name']} - {plan['price']}₽*

⏰ *Длительность:* {plan['days']} дней

*Включает:*
"""
        for feature in plan['features']:
            text += f"{feature}\n"
        
        return text
