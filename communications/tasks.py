"""
Celery tasks for background processing
"""

from celery import shared_task
import logging
from django.utils import timezone
from .models import EmailAccount, EmailQueue
from .email_handler import EmailHandler

logger = logging.getLogger(__name__)


@shared_task
def sync_all_email_accounts():
    """Sync all active email accounts"""
    accounts = EmailAccount.objects.filter(is_active=True, sync_enabled=True)
    
    total_synced = 0
    for account in accounts:
        try:
            count = sync_email_account.delay(account.id)
            total_synced += 1
        except Exception as e:
            logger.error(f"Error queuing sync for {account.email_address}: {str(e)}")
    
    logger.info(f"Queued sync for {total_synced} email accounts")
    return total_synced


@shared_task
def sync_email_account(account_id):
    """Sync a single email account"""
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
        logger.error(f"Error syncing email account {account_id}: {str(e)}")
        return 0


@shared_task
def process_email_queue():
    """Process pending emails in the queue"""
    pending_emails = EmailQueue.objects.filter(
        status='pending',
        scheduled_at__lte=timezone.now()
    ).order_by('scheduled_at')[:50]  # Process 50 at a time
    
    processed = 0
    for queued_email in pending_emails:
        try:
            send_queued_email.delay(queued_email.id)
            processed += 1
        except Exception as e:
            logger.error(f"Error queuing email {queued_email.id}: {str(e)}")
    
    logger.info(f"Queued {processed} emails for sending")
    return processed


@shared_task
def send_queued_email(queue_id):
    """Send a single queued email"""
    try:
        queued_email = EmailQueue.objects.get(id=queue_id)
        
        # Mark as sending
        queued_email.status = 'sending'
        queued_email.save()
        
        # Get email handler
        handler = EmailHandler(queued_email.email_account)
        
        # Send email
        success, message = handler.send_email(
            to_addresses=queued_email.to_addresses,
            subject=queued_email.subject,
            body=queued_email.plain_body,
            html_body=queued_email.html_body,
            cc_addresses=queued_email.cc_addresses,
            bcc_addresses=queued_email.bcc_addresses,
            conversation=queued_email.conversation
        )
        
        if success:
            queued_email.status = 'sent'
            queued_email.sent_at = timezone.now()
            queued_email.save()
            logger.info(f"Sent queued email {queue_id}")
            return True
        else:
            # Retry logic
            queued_email.retry_count += 1
            
            if queued_email.retry_count >= queued_email.max_retries:
                queued_email.status = 'failed'
                queued_email.last_error = message
            else:
                queued_email.status = 'pending'
                queued_email.last_error = message
            
            queued_email.save()
            logger.warning(f"Failed to send queued email {queue_id}: {message}")
            return False
        
    except EmailQueue.DoesNotExist:
        logger.error(f"Queued email not found: {queue_id}")
        return False
    except Exception as e:
        logger.error(f"Error sending queued email {queue_id}: {str(e)}")
        
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
        
        return False


@shared_task
def distribute_unassigned_conversations():
    """Distribute unassigned conversations among agents"""
    from .assignment_system import distribute_workload
    
    count = distribute_workload()
    logger.info(f"Distributed {count} conversations")
    return count
