"""
DRF Serializers for Communications API
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import (
    Contact, Conversation, Message, InternalNote, QuickReply,
    WhatsAppAccount, WhatsAppMessage, EmailAccount, EmailMessage,
    EmailTemplate, EmailSignature
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class ContactSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    
    class Meta:
        model = Contact
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):
    sender_info = UserSerializer(source='sender', read_only=True)
    
    class Meta:
        model = Message
        fields = '__all__'


class InternalNoteSerializer(serializers.ModelSerializer):
    author_info = UserSerializer(source='author', read_only=True)
    
    class Meta:
        model = InternalNote
        fields = '__all__'


class ConversationSerializer(serializers.ModelSerializer):
    contact_info = ContactSerializer(source='contact', read_only=True)
    assigned_to_info = UserSerializer(source='assigned_to', read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    internal_notes = InternalNoteSerializer(many=True, read_only=True)
    
    class Meta:
        model = Conversation
        fields = '__all__'


class ConversationListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views"""
    contact_name = serializers.CharField(source='contact.client.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ['id', 'contact_name', 'channel', 'status', 'assigned_to_name', 
                  'priority', 'subject', 'last_message_at', 'last_message_preview',
                  'message_count', 'created_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()


class QuickReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuickReply
        fields = '__all__'


class WhatsAppAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppAccount
        fields = '__all__'
        extra_kwargs = {
            'access_token': {'write_only': True},
            'webhook_verify_token': {'write_only': True}
        }


class EmailAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAccount
        fields = '__all__'
        extra_kwargs = {
            'encrypted_password': {'write_only': True}
        }


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = '__all__'


class EmailSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSignature
        fields = '__all__'
