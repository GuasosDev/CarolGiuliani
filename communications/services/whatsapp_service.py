import requests
from django.conf import settings


class WhatsAppService:

    @staticmethod
    def send_text_message(account, to, message_text):

        if settings.DEBUG:
            return {
                "mock": True,
                "to": to,
                "message": message_text,
                "status": "sent (mock)"
            }
        url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_API_VERSION}/{account.phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {account.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message_text},
        }

        response = requests.post(url, json=payload, headers=headers)
        return response.json()
