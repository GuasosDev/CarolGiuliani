"""
WhatsApp Business API Handler
Handles webhook events and message sending via WhatsApp Business API
"""

import requests
from django.core.files.base import ContentFile
import json
import logging
import io
import os
import shutil
import subprocess
import tempfile
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
    
    # Eliminar todo lo que no sea dígito
    digits = "".join(filter(str.isdigit, str(number)))
    
    if not digits:
        return ""
    
    # Lógica para Argentina (54) + 9 + número
    if digits.startswith("54"):
        if not digits.startswith("549"):
            # Insertar el 9 después del 54
            digits = "549" + digits[2:]
    else:
        # Si empieza con 0, quitarlo
        if digits.startswith("0"):
            digits = digits[1:]
        # Prepend 549
        digits = "549" + digits
        
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
    
    def send_text_message(self, to_number, message_text, conversation=None, sender_user=None, metadata=None):
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
                msg_meta = {'to': to_number}
                if metadata and isinstance(metadata, dict):
                    msg_meta.update(metadata)
                message = Message.objects.create(
                    conversation=conversation,
                    message_type='whatsapp',
                    direction='outbound',
                    content=message_text,
                    sender=sender_user,
                    metadata=msg_meta
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
    
    def send_media_message(self, to_number, media_type, media_id, caption=None, filename=None, conversation=None, uploaded_file=None, sender_user=None):
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
                    sender=sender_user,
                    metadata={'to': to_number, 'media_type': media_type}
                )
                if uploaded_file:
                    message.file.save(
                        uploaded_file.name,
                        uploaded_file,
                        save=True
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
        content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
        name = (getattr(uploaded_file, 'name', '') or '').lower()

        if content_type.startswith('image/') or name.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            return 'image'
        if content_type.startswith('video/') or name.endswith(('.mp4', '.mov')):
            return 'video'
        if content_type.startswith('audio/') or name.endswith(('.mp3', '.ogg', '.wav', '.webm', '.opus', '.m4a')):
            return 'audio'
        
        return 'document'

    def _convert_webm_to_ogg(self, uploaded_file):
        ffmpeg = os.getenv('FFMPEG_BINARY', '').strip() or shutil.which('ffmpeg')
        if not ffmpeg:
            for candidate in ('/usr/bin/ffmpeg', '/bin/ffmpeg', '/usr/local/bin/ffmpeg'):
                if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                    ffmpeg = candidate
                    break
        if not ffmpeg:
            return False, 'No se encontró ffmpeg en el servidor. Instalá ffmpeg o usá un navegador que grabe en audio/ogg o audio/mp4.'

        original_name = getattr(uploaded_file, 'name', 'voice.webm')
        base, _ext = os.path.splitext(original_name)
        out_name = f"{base}.ogg"

        raw = uploaded_file.read()
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, 'input.webm')
            out_path = os.path.join(tmp, 'output.ogg')
            with open(in_path, 'wb') as f:
                f.write(raw)

            proc = subprocess.run(
                [ffmpeg, '-y', '-i', in_path, '-c:a', 'libopus', out_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if proc.returncode != 0 or not os.path.exists(out_path):
                return False, proc.stderr or 'ffmpeg error'

            with open(out_path, 'rb') as f:
                converted = f.read()

        return True, (out_name, io.BytesIO(converted), 'audio/ogg')

    def upload_media(self, uploaded_file):
        url = f"{self.api_url}/{self.account.phone_number_id}/media"
        headers = {
            'Authorization': f'Bearer {self.account.access_token}',
        }

        content_type = getattr(uploaded_file, 'content_type', None)
        filename = getattr(uploaded_file, 'name', 'attachment')

        normalized_ct = (content_type or '').split(';')[0].strip().lower()
        if normalized_ct == 'audio/webm' or (isinstance(filename, str) and filename.lower().endswith('.webm')):
            ok, converted = self._convert_webm_to_ogg(uploaded_file)
            if not ok:
                return False, {'error': {'message': str(converted)}}
            filename, file_handle, content_type = converted
        else:
            file_handle = getattr(uploaded_file, 'file', uploaded_file)

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
    
    def send_template_message(self, to_number, template_name, language_code, components=None, conversation=None, content_for_db=None, sender_user=None):
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

            if conversation:
                content = content_for_db if content_for_db is not None else f"📄 Plantilla: {template_name}"
                message = Message.objects.create(
                    conversation=conversation,
                    message_type='whatsapp',
                    direction='outbound',
                    content=content,
                    sender=sender_user,
                    metadata={
                        'to': to_number,
                        'template_name': template_name,
                        'template_language': language_code,
                        'template_components': components or []
                    }
                )

                WhatsAppMessage.objects.create(
                    message=message,
                    whatsapp_account=self.account,
                    whatsapp_message_id=message_id,
                    wa_message_type='text',
                    delivery_status='sent',
                    template_name=template_name,
                    template_language=language_code
                )
            
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
        resolved_mime_type = None
        mime_type = None
        
        if message_type == 'text':
            content = msg_data.get('text', {}).get('body', '')
        elif message_type in ['image', 'document', 'audio', 'video', 'sticker']:
            media_data = msg_data.get(message_type, {})
            media_id = media_data.get('id')
            caption = media_data.get('caption', '')
            mime_type = media_data.get('mime_type')
            resolved_mime_type = mime_type
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

        was_closed = (conversation.status == 'closed')
        
        # Create message
        base_metadata = {'from': from_number, 'timestamp': timestamp}
        if media_id:
            base_metadata.update({'media_type': message_type, 'media_id': media_id})

        message = Message.objects.create(
            conversation=conversation,
            message_type='whatsapp',
            direction='inbound',
            content=content,
            sender_name=value.get('contacts', [{}])[0].get('profile', {}).get('name', from_number),
            metadata=base_metadata
        )
        # ── Descargar y guardar adjunto ─────────────────────────────
        if media_id:
            try:
                access_token = whatsapp_account.access_token
                resolved_mime_type = (mime_type or "").strip()

                # 1. Obtener URL del archivo
                media_info_url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_API_VERSION}/{media_id}"
                headers = {"Authorization": f"Bearer {access_token}"}
                media_response = requests.get(media_info_url, headers=headers)
                media_json = media_response.json()
                media_url = media_json.get("url")
                resolved_mime_type = (media_json.get("mime_type") or mime_type or "").strip()
                normalized_mime = resolved_mime_type.split(";")[0].strip().lower()

                if media_url:
                    # 2. Descargar archivo
                    file_response = requests.get(media_url, headers=headers)

                    if file_response.status_code == 200:
                        extension = "bin"
                        if normalized_mime:
                            if normalized_mime == "audio/mpeg":
                                extension = "mp3"
                            elif normalized_mime == "audio/mp4":
                                extension = "m4a"
                            elif "/" in normalized_mime:
                                extension = normalized_mime.split("/")[-1] or "bin"

                        filename = f"wa_{message_id}.{extension}"

                        # 3. Guardar en el modelo (ajustar campo si no es 'file')
                        message.file.save(
                            filename,
                            ContentFile(file_response.content),
                            save=True
                        )
                        message.metadata['media_mime_type'] = resolved_mime_type or normalized_mime
                        message.metadata['media_url'] = media_url
                        message.save(update_fields=['metadata'])

            except Exception as e:
                logger.error(f"Error downloading media: {str(e)}")
        # ───────────────────────────────────────────────────────────
        
        # Create WhatsApp-specific message data
        WhatsAppMessage.objects.create(
            message=message,
            whatsapp_account=whatsapp_account,
            whatsapp_message_id=message_id,
            wa_message_type=message_type,
            media_id=media_id,
            media_url=media_url,
            media_mime_type=resolved_mime_type,
            caption=caption,
            delivery_status='delivered'
        )

        if message_type == 'audio' and message.file:
            try:
                from .tasks import transcribe_whatsapp_audio
                message.metadata = message.metadata or {}
                message.metadata['transcription_status'] = 'queued'
                message.save(update_fields=['metadata'])
                transcribe_whatsapp_audio.delay(message.pk)
            except Exception as e:
                logger.error(f"Error queuing audio transcription: {str(e)}")
        
        # Mark as read
        handler = WhatsAppHandler(whatsapp_account)
        handler.mark_message_as_read(message_id)

        # ── Welcome Menu Logic (only for text messages) ──────────────────────
        if message_type == 'text':
            _handle_welcome_menu(handler, contact, conversation, content, force_show=was_closed)
        # ─────────────────────────────────────────────────────────────────────

        # Broadcast via WebSocket
        from .websocket_utils import broadcast_new_message
        broadcast_new_message(message)
        
        logger.info(f"Processed incoming WhatsApp message: {message_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        return False


def _agent_started_whatsapp_outreach_today(contact, start, end):
    """
    True si hoy el contacto recibió primero un mensaje nuestro (p. ej. plantilla),
    no si él escribió primero.

    Así, si el agente contactó al cliente y éste responde, no se le muestra
    el menú de bienvenida como si hubiera iniciado él el chat.
    """
    qs = (
        Message.objects.filter(
            conversation__contact=contact,
            message_type='whatsapp',
            created_at__gte=start,
            created_at__lt=end,
        )
        .order_by('created_at', 'id')
    )

    for msg in qs.iterator():
        meta = msg.metadata or {}
        # Ignorar el propio menú de bienvenida (también es outbound)
        if msg.direction == 'outbound' and meta.get('welcome_menu'):
            continue
        if msg.direction == 'outbound':
            return True
        if msg.direction == 'inbound':
            return False
    return False


def _handle_welcome_menu(handler, contact, conversation, text, force_show=False):
    """
    Show the welcome menu on the first inbound text of the day, then keep it
    suppressed until the next day (00:00 local time), unless forced.

    No mostrar si hoy la conversación la inició el equipo (plantilla / outbound).
    """
    text_stripped = text.strip().lower()
    if not text_stripped:
        return

    from django.utils import timezone
    from datetime import timedelta

    now = timezone.localtime(timezone.now())
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    # 1. Check if contact is waiting to select from a previously sent menu
    try:
        menu_state = ContactMenuState.objects.select_related('menu').get(contact=contact)
        state_created = timezone.localtime(menu_state.created_at) if menu_state.created_at else None
        if state_created and state_created < start:
            menu_state.delete()
            menu_state = None
        else:
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
                    invalid_msg = "Opción no válida. Por favor respondé con un número del menú enviado anteriormente."
                    handler.send_text_message(contact.whatsapp_number, invalid_msg, conversation=conversation)
                    return
            except ValueError:
                return
    except ContactMenuState.DoesNotExist:
        pass

    # Si hoy iniciamos nosotros (plantilla / mensaje saliente), no tratar la
    # respuesta del cliente como "primer contacto" con menú de bienvenida.
    if _agent_started_whatsapp_outreach_today(contact, start, end):
        logger.info(
            "Skip welcome menu for contact %s: agent-initiated outreach today",
            contact.pk,
        )
        return

    # 2. Show menu for the first inbound text of the day
    active_menu = WelcomeMenu.objects.filter(is_active=True).first()
    if not active_menu:
        return

    if not force_show:
        already_shown_today = Message.objects.filter(
            conversation__contact=contact,
            message_type='whatsapp',
            direction='outbound',
            created_at__gte=start,
            created_at__lt=end,
            metadata__welcome_menu=True,
            metadata__welcome_menu_id=active_menu.id,
        ).exists()
        if already_shown_today:
            return

    menu_text = active_menu.build_message_text()
    handler.send_text_message(
        contact.whatsapp_number,
        menu_text,
        conversation=conversation,
        metadata={'welcome_menu': True, 'welcome_menu_id': active_menu.id}
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
