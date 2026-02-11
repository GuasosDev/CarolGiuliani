"""
WebSocket utility functions for broadcasting messages
"""

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def broadcast_new_message(message):
    """Broadcast a new message to relevant users"""
    channel_layer = get_channel_layer()
    
    # Serialize message data
    message_data = {
        'id': message.id,
        'conversation_id': message.conversation.id,
        'content': message.content,
        'direction': message.direction,
        'message_type': message.message_type,
        'sender': message.sender.username if message.sender else message.sender_name,
        'created_at': message.created_at.isoformat(),
    }
    
    # Send to assigned agent
    if message.conversation.assigned_to:
        async_to_sync(channel_layer.group_send)(
            f"user_{message.conversation.assigned_to.id}",
            {
                'type': 'new_message',
                'message': message_data
            }
        )
    
    # Send to all supervisors/admins
    from django.contrib.auth.models import User
    supervisors = User.objects.filter(is_staff=True, is_superuser=True)
    for supervisor in supervisors:
        async_to_sync(channel_layer.group_send)(
            f"user_{supervisor.id}",
            {
                'type': 'new_message',
                'message': message_data
            }
        )


def broadcast_conversation_assignment(conversation, agent):
    """Broadcast conversation assignment to the agent"""
    channel_layer = get_channel_layer()
    
    conversation_data = {
        'id': conversation.id,
        'contact_name': conversation.contact.client.name if conversation.contact.client else 'Unknown',
        'channel': conversation.channel,
        'status': conversation.status,
        'subject': conversation.subject,
        'created_at': conversation.created_at.isoformat(),
    }
    
    async_to_sync(channel_layer.group_send)(
        f"user_{agent.id}",
        {
            'type': 'conversation_assigned',
            'conversation': conversation_data
        }
    )


def broadcast_message_status_update(message_id, status):
    """Broadcast message status update"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        "communications",
        {
            'type': 'message_status_update',
            'message_id': message_id,
            'status': status
        }
    )
