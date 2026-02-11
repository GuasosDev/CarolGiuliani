"""
WebSocket consumer for real-time communication updates
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User


class CommunicationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join user-specific group
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        # Join general communications group
        await self.channel_layer.group_add(
            "communications",
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to communications channel'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave groups
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        
        await self.channel_layer.group_discard(
            "communications",
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'typing':
                # Broadcast typing indicator
                conversation_id = data.get('conversation_id')
                await self.channel_layer.group_send(
                    f"conversation_{conversation_id}",
                    {
                        'type': 'typing_indicator',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'is_typing': data.get('is_typing', True)
                    }
                )
            
            elif message_type == 'mark_read':
                # Mark message as read
                message_id = data.get('message_id')
                await self.mark_message_read(message_id)
        
        except json.JSONDecodeError:
            pass
    
    async def new_message(self, event):
        """Handle new message broadcast"""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))
    
    async def message_status_update(self, event):
        """Handle message status update"""
        await self.send(text_data=json.dumps({
            'type': 'message_status_update',
            'message_id': event['message_id'],
            'status': event['status']
        }))
    
    async def conversation_assigned(self, event):
        """Handle conversation assignment"""
        await self.send(text_data=json.dumps({
            'type': 'conversation_assigned',
            'conversation': event['conversation']
        }))
    
    async def typing_indicator(self, event):
        """Handle typing indicator"""
        # Don't send typing indicator back to the sender
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }))
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark a message as read in the database"""
        from .models import Message
        try:
            message = Message.objects.get(id=message_id)
            message.mark_as_read()
        except Message.DoesNotExist:
            pass
