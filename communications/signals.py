from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message, Conversation
from django.utils import timezone


@receiver(post_save, sender=Message)
def update_conversation_on_message(sender, instance, created, **kwargs):
    """Update conversation's last_message_at and preview when a new message is created"""
    if created:
        conversation = instance.conversation
        conversation.last_message_at = instance.created_at
        conversation.last_message_preview = instance.content[:100]  # First 100 chars
        conversation.updated_at = timezone.now()
        conversation.save()
