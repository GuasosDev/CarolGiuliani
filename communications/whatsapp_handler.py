"""
WhatsApp Business API Handler
Handles webhook events and message sending via WhatsApp Business API
"""

import requests
import json
import logging
from django.conf import settings
from django.utils import timezone
from .models import (
    WhatsAppAccount, WhatsAppMessage, Message, Conversation,
    Contact, ConversationAssignment
)
from .assignment_system import assign_conversation_to_agent

logger = logging.getLogger(__name__)


class WhatsAppHandler:
    """Handler for WhatsApp Business API operations"""
    
    def __init__(self, whatsapp_account):
        self.account = whatsapp_account
        self.api_url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_API_VERSION}"
        self.headers = {
            'Authorization': f'Bearer {self.account.access_token}',
            'Content-Type': 'application/json',
        }
    
    def send_text_message(self, to_number, message_text, conversation=None):
        """Send a text message via WhatsApp"""
        url = f"{self.api_url}/{self.account.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_text
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')
            
            # Create message record
            if conversation:
                message = Message.objects.create(
                    conversation=conversation,
                    message_type='whatsapp',
                    direction='outbound',
                    content=message_text,
                    metadata={'to': to_number}
                )
                
                WhatsAppMessage.objects.create(
                    message=message,
                    whatsapp_account=self.account,
                    whatsapp_message_id=message_id,
                    wa_message_type='text',
                    delivery_status='sent'
                )
            
            logger.info(f"WhatsApp message sent: {message_id}")
            return True, message_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False, str(e)
    
    def send_media_message(self, to_number, media_type, media_id, caption=None, conversation=None):
        """Send a media message (image, document, audio, video)"""
        url = f"{self.api_url}/{self.account.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": media_type,
            media_type: {
                "id": media_id
            }
        }
        
        if caption and media_type in ['image', 'document', 'video']:
            payload[media_type]['caption'] = caption
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')
            
            # Create message record
            if conversation:
                message = Message.objects.create(
                    conversation=conversation,
                    message_type='whatsapp',
                    direction='outbound',
                    content=caption or f"[{media_type.upper()}]",
                    metadata={'to': to_number, 'media_type': media_type}
                )
                
                WhatsAppMessage.objects.create(
                    message=message,
                    whatsapp_account=self.account,
                    whatsapp_message_id=message_id,
                    wa_message_type=media_type,
                    media_id=media_id,
                    caption=caption,
                    delivery_status='sent'
                )
            
            logger.info(f"WhatsApp media message sent: {message_id}")
            return True, message_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending WhatsApp media message: {str(e)}")
            return False, str(e)
    
    def send_template_message(self, to_number, template_name, language_code, components=None):
        """Send a template message"""
        url = f"{self.api_url}/{self.account.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }
        
        if components:
            payload['template']['components'] = components
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')
            
            logger.info(f"WhatsApp template message sent: {message_id}")
            return True, message_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending WhatsApp template message: {str(e)}")
            return False, str(e)
    
    def download_media(self, media_id):
        """Download media file from WhatsApp"""
        # First, get media URL
        url = f"{self.api_url}/{media_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            media_data = response.json()
            media_url = media_data.get('url')
            mime_type = media_data.get('mime_type')
            
            # Download the actual file
            media_response = requests.get(media_url, headers=self.headers)
            media_response.raise_for_status()
            
            return media_response.content, mime_type
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading WhatsApp media: {str(e)}")
            return None, None
    
    def mark_message_as_read(self, message_id):
        """Mark a message as read"""
        url = f"{self.api_url}/{self.account.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error marking message as read: {str(e)}")
            return False


def process_whatsapp_webhook(webhook_data):
    """Process incoming WhatsApp webhook data"""
    try:
        entry = webhook_data.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        
        # Get metadata
        metadata = value.get('metadata', {})
        phone_number_id = metadata.get('phone_number_id')
        
        # Get WhatsApp account
        try:
            whatsapp_account = WhatsAppAccount.objects.get(phone_number_id=phone_number_id)
        except WhatsAppAccount.DoesNotExist:
            logger.error(f"WhatsApp account not found: {phone_number_id}")
            return False
        
        # Process messages
        messages = value.get('messages', [])
        for msg in messages:
            process_incoming_message(whatsapp_account, msg, value)
        
        # Process status updates
        statuses = value.get('statuses', [])
        for status in statuses:
            process_status_update(status)
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {str(e)}")
        return False


def process_incoming_message(whatsapp_account, msg_data, value):
    """Process an incoming WhatsApp message"""
    try:
        from_number = msg_data.get('from')
        message_id = msg_data.get('id')
        timestamp = msg_data.get('timestamp')
        message_type = msg_data.get('type')
        
        # Extract message content based on type
        content = ""
        media_id = None
        media_url = None
        caption = None
        
        if message_type == 'text':
            content = msg_data.get('text', {}).get('body', '')
        elif message_type in ['image', 'document', 'audio', 'video', 'sticker']:
            media_data = msg_data.get(message_type, {})
            media_id = media_data.get('id')
            caption = media_data.get('caption', '')
            content = caption or f"[{message_type.upper()}]"
        elif message_type == 'location':
            location = msg_data.get('location', {})
            content = f"Location: {location.get('latitude')}, {location.get('longitude')}"
        elif message_type == 'contacts':
            content = "[CONTACT CARD]"
        
        # Get or create contact
        contact, _ = Contact.objects.get_or_create(
            whatsapp_number=from_number,
            defaults={
                'client_id': None,  # Will need to be linked manually or via matching
                'preferred_channel': 'whatsapp'
            }
        )
        
        # Get or create conversation
        conversation = Conversation.objects.filter(
            contact=contact,
            channel='whatsapp',
            status__in=['open', 'assigned', 'pending']
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                contact=contact,
                channel='whatsapp',
                status='open',
                priority='normal'
            )
            
            # Auto-assign to an agent
            assign_conversation_to_agent(conversation)
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            message_type='whatsapp',
            direction='inbound',
            content=content,
            sender_name=value.get('contacts', [{}])[0].get('profile', {}).get('name', from_number),
            metadata={'from': from_number, 'timestamp': timestamp}
        )
        
        # Create WhatsApp-specific message data
        WhatsAppMessage.objects.create(
            message=message,
            whatsapp_account=whatsapp_account,
            whatsapp_message_id=message_id,
            wa_message_type=message_type,
            media_id=media_id,
            caption=caption,
            delivery_status='delivered'
        )
        
        # Mark as read
        handler = WhatsAppHandler(whatsapp_account)
        handler.mark_message_as_read(message_id)
        
        # Broadcast via WebSocket
        from .websocket_utils import broadcast_new_message
        broadcast_new_message(message)
        
        logger.info(f"Processed incoming WhatsApp message: {message_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        return False


def process_status_update(status_data):
    """Process message status update (sent, delivered, read, failed)"""
    try:
        message_id = status_data.get('id')
        status = status_data.get('status')
        
        # Update WhatsApp message status
        try:
            wa_message = WhatsAppMessage.objects.get(whatsapp_message_id=message_id)
            wa_message.delivery_status = status
            
            if status == 'failed':
                error = status_data.get('errors', [{}])[0]
                wa_message.error_message = error.get('message', 'Unknown error')
            
            wa_message.save()
            
            # If read, mark the base message as read too
            if status == 'read':
                wa_message.message.mark_as_read()
            
            logger.info(f"Updated message status: {message_id} -> {status}")
            
        except WhatsAppMessage.DoesNotExist:
            logger.warning(f"WhatsApp message not found for status update: {message_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing status update: {str(e)}")
        return False
