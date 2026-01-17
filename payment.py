import logging

logger = logging.getLogger(__name__)

class SimplePayment:
    def __init__(self):
        self.payments = {}
    
    def create_payment(self, user_id, amount, plan_type):
        """Создает платеж"""
        try:
            payment_id = f"pay_{user_id}_{len(self.payments)}"
            self.payments[payment_id] = {
                'user_id': user_id,
                'amount': amount,
                'plan_type': plan_type,
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            return {
                'success': True,
                'payment_id': payment_id,
                'message': f"Тестовый платеж создан. ID: {payment_id}"
            }
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            return {'success': False, 'error': str(e)}

# Глобальный экземпляр
payment = SimplePayment()
