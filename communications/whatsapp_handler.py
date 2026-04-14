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
    Contact, ConversationAssignment, WelcomeMenu, ContactMenuState
)
from .assignment_system import assign_conversation_to_agent

logger = logging.getLogger(__name__)


def normalize_phone_number(number):
    if not number:
        return number
    digits = ''.join(ch for ch in str(number) if ch.isdigit())
    return digits


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
        to_number = normalize_phone_number(to_number)
        
        if not to_number:
            logger.error("Error sending WhatsApp message: No phone number provided")
            return False, "El destinatario no tiene un número de teléfono válido configurado."

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
            
        except requests.exceptions.HTTPError as e:
            error_body = None
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text
            logger.error(f"Error sending WhatsApp message: {error_body}")
            return False, error_body
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False, str(e)
    
    def send_media_message(self, to_number, media_type, media_id, caption=None, filename=None, conversation=None):
        """Send a media message (image, document, audio, video)"""
        to_number = normalize_phone_number(to_number)
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
        if filename and media_type == 'document':
            payload[media_type]['filename'] = filename
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')
            
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
            
        except requests.exceptions.HTTPError as e:
            error_body = None
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text
            logger.error(f"Error sending WhatsApp media message: {error_body}")
            return False, error_body
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending WhatsApp media message: {str(e)}")
            return False, str(e)

    def detect_media_type(self, uploaded_file):
        content_type = (getattr(uploaded_file, 'content_type', None) or '').lower()
        if content_type.startswith('image/'):
            return 'image'
        if content_type.startswith('video/'):
            return 'video'
        if content_type.startswith('audio/'):
            return 'audio'
        return 'document'

    def upload_media(self, uploaded_file):
        url = f"{self.api_url}/{self.account.phone_number_id}/media"
        headers = {
            'Authorization': f'Bearer {self.account.access_token}',
        }

        file_handle = getattr(uploaded_file, 'file', uploaded_file)
        content_type = getattr(uploaded_file, 'content_type', None)
        filename = getattr(uploaded_file, 'name', 'attachment')

        files = {
            'file': (filename, file_handle, content_type) if content_type else (filename, file_handle)
        }
        data = {
            'messaging_product': 'whatsapp'
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            media_id = response.json().get('id')
            if not media_id:
                return False, response.json()
            return True, media_id
        except requests.exceptions.HTTPError:
            try:
                return False, response.json()
            except Exception:
                return False, response.text
        except requests.exceptions.RequestException as e:
            return False, str(e)
    
    def send_template_message(self, to_number, template_name, language_code, components=None):
        """Send a template message"""
        to_number = normalize_phone_number(to_number)
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
            
        except requests.exceptions.HTTPError as e:
            error_body = None
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text
            logger.error(f"Error sending WhatsApp template message: {error_body}")
            return False, error_body
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
        
        # Try to find existing contact by matching the last 10 digits (common for AR numbers)
        normalized_from = normalize_phone_number(from_number)
        contact = Contact.objects.filter(whatsapp_number=from_number).first()
        
        if not contact and normalized_from:
            # Try matching normalized exact
            contact = Contact.objects.filter(whatsapp_number=normalized_from).first()

        # If we found a contact but it's not linked to a client, try to find one that IS
        if contact and not contact.client and normalized_from and len(normalized_from) >= 10:
            suffix = normalized_from[-10:]
            better_contact = Contact.objects.filter(
                whatsapp_number__endswith=suffix
            ).exclude(client__isnull=True).first()
            if better_contact:
                contact = better_contact
                logger.info(f"Preferred contact with client: {contact.client.name}")
            
        if not contact and normalized_from and len(normalized_from) >= 10:
            # Try matching suffix (useful for AR +54 9 vs +54)
            suffix = normalized_from[-10:]
            contact = Contact.objects.filter(whatsapp_number__endswith=suffix).first()

        if not contact and normalized_from and len(normalized_from) >= 10:
            # Try matching via the linked client's phone number
            from clients.models import Client
            suffix = normalized_from[-10:]
            client_match = Client.objects.filter(phone__endswith=suffix).first()
            if client_match:
                # Find or create a contact for this client
                contact, created = Contact.objects.get_or_create(
                    client=client_match,
                    defaults={'whatsapp_number': from_number, 'preferred_channel': 'whatsapp'}
                )
                if not contact.whatsapp_number:
                    # Save the WA number so future lookups are fast
                    contact.whatsapp_number = from_number
                    contact.save(update_fields=['whatsapp_number'])
                logger.info(f"Matched incoming number {from_number} to client {client_match.name}")

        if not contact:
            contact = Contact.objects.create(
                whatsapp_number=from_number,
                client_id=None,
                preferred_channel='whatsapp'
            )
        
        # Get or create conversation
        conversation = Conversation.objects.filter(
            contact=contact,
            channel='whatsapp',
            status__in=['normal', 'open', 'assigned', 'pending']
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                contact=contact,
                channel='whatsapp',
                status='normal',
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

        # ── Welcome Menu Logic (only for text messages) ──────────────────────
        if message_type == 'text':
            _handle_welcome_menu(handler, contact, conversation, content)
        # ─────────────────────────────────────────────────────────────────────

        # Broadcast via WebSocket
        from .websocket_utils import broadcast_new_message
        broadcast_new_message(message)
        
        logger.info(f"Processed incoming WhatsApp message: {message_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        return False


def _handle_welcome_menu(handler, contact, conversation, text):
    """
    Check if the incoming text matches a welcome menu trigger keyword or
    is a menu selection response. Handles auto-response and conversation routing.
    """
    text_stripped = text.strip().lower()

    # 1. Check if contact is waiting to select from a previously sent menu
    try:
        menu_state = ContactMenuState.objects.select_related('menu').get(contact=contact)
        # Try to parse as a number
        try:
            chosen_number = int(text_stripped)
            item = menu_state.menu.items.filter(number=chosen_number).first()
            if item:
                # Assign to the item's user
                if item.assigned_user:
                    from .assignment_system import reassign_conversation
                    reassign_conversation(conversation, item.assigned_user, item.assigned_user)
                    confirmation = f"✅ Te hemos conectado con {item.label}. En breve te atenderán."
                else:
                    confirmation = f"✅ Seleccionaste {item.label}. En breve te atenderán."
                handler.send_text_message(
                    contact.whatsapp_number,
                    confirmation,
                    conversation=conversation
                )
                menu_state.delete()
                logger.info(f"Menu selection {chosen_number} by contact {contact.pk}: assigned to {item.assigned_user}")
                return
            else:
                # Invalid option – resend the menu
                invalid_msg = f"Opción no válida. Por favor elija un número del menú:\n\n{menu_state.menu.build_message_text()}"
                handler.send_text_message(contact.whatsapp_number, invalid_msg, conversation=conversation)
                return
        except ValueError:
            # Not a number – treat as a new keyword check, clear state
            menu_state.delete()
    except ContactMenuState.DoesNotExist:
        pass

    # 2. Check if the text is a trigger keyword for any active menu
    active_menu = WelcomeMenu.objects.filter(is_active=True).first()
    if not active_menu:
        return

    keywords = [kw.strip().lower() for kw in active_menu.trigger_keywords if kw.strip()]
    if text_stripped in keywords:
        menu_text = active_menu.build_message_text()
        handler.send_text_message(
            contact.whatsapp_number,
            menu_text,
            conversation=conversation
        )
        # Save state so we know this contact is expecting a selection
        ContactMenuState.objects.update_or_create(
            contact=contact,
            defaults={'menu': active_menu}
        )
        logger.info(f"Sent welcome menu '{active_menu.name}' to contact {contact.pk}")


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
