"""
Celery tasks for background processing
"""

"""
Celery tasks for background processing
"""

from celery import shared_task
import logging
import traceback
import os
import requests
from django.utils import timezone
from django.db import transaction
from .models import EmailAccount, EmailQueue, Conversation, Message
from .email_handler import EmailHandler
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def sync_all_email_accounts():
    """Sync all active email accounts"""
    accounts = EmailAccount.objects.filter(is_active=True, sync_enabled=True)

    total = 0
    for account in accounts:
        try:
            sync_email_account.apply_async(args=[account.id])
            total += 1
        except Exception as e:
            logger.error(f"Error queuing sync for {account.email_address}: {str(e)}")

    logger.info(f"Queued sync for {total} email accounts")
    return total


@shared_task
def sync_email_account(account_id):
    try:
        account = EmailAccount.objects.get(id=account_id)
        handler = EmailHandler(account)

        emails = handler.fetch_new_emails()

        logger.info(f"Synced {len(emails)} emails for {account.email_address}")
        return len(emails)

    except EmailAccount.DoesNotExist:
        logger.error(f"Email account not found: {account_id}")
        return 0
    except Exception as e:
        logger.error(f"Error syncing email account {account_id}: {str(e)}\n{traceback.format_exc()}")
        return 0


@shared_task
def process_email_queue():
    """Process pending emails in the queue"""
    pending_emails = EmailQueue.objects.filter(
        status='pending',
        scheduled_at__lte=timezone.now()
    ).order_by('scheduled_at')[:50]

    processed = 0
    for email in pending_emails:
        try:
            send_queued_email.apply_async(args=[email.id])
            processed += 1
        except Exception as e:
            logger.error(f"Error queuing email {email.id}: {str(e)}")

    logger.info(f"Queued {processed} emails for sending")
    return processed


@shared_task(bind=True, max_retries=3, default_retry_delay=60, rate_limit='10/m')
def send_queued_email(self, queue_id):
    """Send a single queued email with retry + concurrency protection"""
    try:
        with transaction.atomic():
            queued_email = EmailQueue.objects.select_for_update().get(id=queue_id)

            # Evitar doble envío
            if queued_email.status == 'sent':
                logger.warning(f"Email {queue_id} already sent")
                return True

            queued_email.status = 'sending'
            queued_email.save()

        handler = EmailHandler(queued_email.email_account)

        # Retrieve attachments if they exist via email_message
        attachments = []
        email_msg = queued_email.email_message
        if email_msg:
            attachments = list(email_msg.attachments.all())

        success, message = handler.send_email(
            to_addresses=queued_email.to_addresses,
            subject=queued_email.subject,
            body=queued_email.plain_body,
            html_body=queued_email.html_body,
            cc_addresses=queued_email.cc_addresses,
            bcc_addresses=queued_email.bcc_addresses,
            conversation=queued_email.conversation,
            attachments=attachments,
            email_msg=email_msg
        )

        if success:
            queued_email.status = 'sent'
            queued_email.sent_at = timezone.now()
            queued_email.save()

            logger.info(f"Sent email {queue_id} to {queued_email.to_addresses}")
            return True

        else:
            raise Exception(message)

    except EmailQueue.DoesNotExist:
        logger.error(f"Queued email not found: {queue_id}")
        return False

    except Exception as e:
        logger.error(f"Error sending email {queue_id}: {str(e)}")

        try:
            queued_email = EmailQueue.objects.get(id=queue_id)
            queued_email.retry_count += 1
            queued_email.last_error = str(e)

            if queued_email.retry_count >= queued_email.max_retries:
                queued_email.status = 'failed'
            else:
                queued_email.status = 'pending'

            queued_email.save()
        except:
            pass

        # Retry automático de Celery
        raise self.retry(exc=e)


@shared_task
def distribute_unassigned_conversations():
    """Distribute unassigned conversations among agents"""
    from .assignment_system import distribute_workload

    count = distribute_workload()
    logger.info(f"Distributed {count} conversations")
    return count


@shared_task
def close_inactive_conversations():
    """Close conversations inactive for 30 minutes"""
    limit = timezone.now() - timedelta(minutes=1)

    conversations = Conversation.objects.filter(
        status="pending",
        updated_at__lt=limit
    )

    count = conversations.count()
    conversations.update(status="closed")

    logger.info(f"Closed {count} inactive conversations")
    return count


@shared_task(bind=True, max_retries=2, default_retry_delay=60, rate_limit='30/m')
def transcribe_whatsapp_audio(self, message_id):
    try:
        message = Message.objects.get(pk=message_id)
    except Message.DoesNotExist:
        return False

    if message.message_type != 'whatsapp':
        return False

    media_type = (message.metadata or {}).get('media_type')
    if media_type != 'audio':
        return False

    if not message.file:
        return False

    metadata = message.metadata or {}
    if metadata.get('transcription'):
        return True

    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        metadata['transcription_status'] = 'missing_api_key'
        message.metadata = metadata
        message.save(update_fields=['metadata'])
        return False

    metadata['transcription_status'] = 'processing'
    message.metadata = metadata
    message.save(update_fields=['metadata'])

    try:
        message.file.open('rb')
        filename = os.path.basename(message.file.name) or 'audio'
        url = 'https://api.openai.com/v1/audio/transcriptions'
        headers = {
            'Authorization': f'Bearer {api_key}',
        }
        data = {
            'model': 'whisper-1',
            'response_format': 'json',
            'language': 'es',
        }
        files = {
            'file': (filename, message.file.file),
        }

        response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
        if response.status_code >= 400:
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text
            metadata['transcription_status'] = 'error'
            metadata['transcription_error'] = error_body
            message.metadata = metadata
            message.save(update_fields=['metadata'])
            return False

        result = response.json()
        text = (result.get('text') or '').strip()

        metadata['transcription'] = text
        metadata['transcription_status'] = 'done'
        message.metadata = metadata
        message.save(update_fields=['metadata'])
        return True

    except Exception as e:
        metadata['transcription_status'] = 'error'
        metadata['transcription_error'] = str(e)
        message.metadata = metadata
        message.save(update_fields=['metadata'])
        raise self.retry(exc=e)
    finally:
        try:
            message.file.close()
        except Exception:
            pass
