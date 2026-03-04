from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message


@receiver(post_save, sender=Message)
def update_conversation_on_new_message(sender, instance, created, **kwargs):
    if not created:
        return

    conversation = instance.conversation

    conversation.last_message_at = instance.created_at
    conversation.last_message_preview = instance.content[:200]

    # Si estaba cerrada y entra mensaje entrante → reabrir
    if instance.direction == 'inbound' and conversation.status == 'closed':
        conversation.status = 'open'
        conversation.closed_at = None

    conversation.save(update_fields=[
        'last_message_at',
        'last_message_preview',
        'status',
        'closed_at',
        'updated_at'
    ])
