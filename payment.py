import hashlib
import hmac
import base64
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class YookassaPayment:
    def __init__(self, shop_id: str, secret_key: str):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.base_url = "https://api.yookassa.ru/v3"
    
    def create_payment_link(self, amount: float, description: str, user_id: int, plan_type: str):
        try:
            headers = {
                'Authorization': f'Basic {self._get_auth_token()}',
                'Content-Type': 'application/json',
                'Idempotence-Key': self._generate_idempotence_key(user_id, plan_type)
            }
            
            payload = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "payment_method_data": {
                    "type": "bank_card"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/"
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "plan_type": plan_type,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            response = requests.post(
                f"{self.base_url}/payments",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "payment_id": data.get("id"),
                    "confirmation_url": data.get("confirmation", {}).get("confirmation_url"),
                    "message": f"💳 *Оплата подписки*\n\nСумма: {amount} ₽\n\n[Перейти к оплате]({data.get('confirmation', {}).get('confirmation_url')})"
                }
            else:
                logger.error(f"Payment creation failed: {response.text}")
                return {"success": False, "error": "Ошибка создания платежа"}
                
        except Exception as e:
            logger.error(f"Error in create_payment_link: {e}")
            return {"success": False, "error": str(e)}
    
    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        try:
            digest = hmac.new(
                self.secret_key.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(digest, signature)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False
    
    def _get_auth_token(self) -> str:
        auth_string = f"{self.shop_id}:{self.secret_key}"
        return base64.b64encode(auth_string.encode()).decode()
    
    def _generate_idempotence_key(self, user_id: int, plan_type: str) -> str:
        timestamp = datetime.now().isoformat()
        string = f"{user_id}_{plan_type}_{timestamp}"
        return hashlib.md5(string.encode()).hexdigest()
