"""
REST API Views for Communications
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from ..models import (
    Contact, Conversation, Message, InternalNote, QuickReply,
    WhatsAppAccount, EmailAccount, EmailTemplate, EmailSignature
)
from .serializers import (
    ContactSerializer, ConversationSerializer, ConversationListSerializer,
    MessageSerializer, InternalNoteSerializer, QuickReplySerializer,
    WhatsAppAccountSerializer, EmailAccountSerializer,
    EmailTemplateSerializer, EmailSignatureSerializer
)
from .permissions import IsAgentOrSupervisor, IsSupervisorOrAdmin, IsAssignedAgent
from ..whatsapp_handler import WhatsAppHandler
from ..email_handler import EmailHandler
from ..assignment_system import assign_conversation_to_agent, reassign_conversation


class ConversationViewSet(viewsets.ModelViewSet):
    """API endpoint for conversations"""
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.all()
        
        # Filter by assigned agent unless supervisor/admin
        if not (user.is_superuser or user.groups.filter(name='Supervisor').exists()):
            queryset = queryset.filter(assigned_to=user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by channel
        channel_filter = self.request.query_params.get('channel')
        if channel_filter:
            queryset = queryset.filter(channel=channel_filter)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(contact__client__name__icontains=search) |
                Q(subject__icontains=search) |
                Q(last_message_preview__icontains=search)
            )
        
        return queryset.order_by('-updated_at')
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign conversation to an agent"""
        conversation = self.get_object()
        agent_id = request.data.get('agent_id')
        
        from django.contrib.auth.models import User
        try:
            agent = User.objects.get(id=agent_id)
            reassign_conversation(conversation, agent, request.user)
            return Response({'status': 'assigned'})
        except User.DoesNotExist:
            return Response({'error': 'Agent not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a conversation"""
        conversation = self.get_object()
        conversation.close()
        return Response({'status': 'closed'})
    
    @action(detail=False, methods=['get'])
    def my_conversations(self, request):
        """Get conversations assigned to current user"""
        conversations = Conversation.objects.filter(
            assigned_to=request.user,
            status__in=['normal', 'pending']
        ).order_by('-updated_at')
        
        serializer = self.get_serializer(conversations, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    """API endpoint for messages"""
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by conversation
        conversation_id = self.request.query_params.get('conversation_id')
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        
        return queryset.order_by('created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark message as read"""
        message = self.get_object()
        message.mark_as_read()
        return Response({'status': 'read'})


class InternalNoteViewSet(viewsets.ModelViewSet):
    """API endpoint for internal notes"""
    queryset = InternalNote.objects.all()
    serializer_class = InternalNoteSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class QuickReplyViewSet(viewsets.ModelViewSet):
    """API endpoint for quick replies"""
    queryset = QuickReply.objects.all()
    serializer_class = QuickReplySerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Show global quick replies and user's own
        queryset = queryset.filter(
            Q(is_global=True) | Q(created_by=self.request.user)
        )
        
        # Filter by channel
        channel = self.request.query_params.get('channel')
        if channel:
            queryset = queryset.filter(Q(channel=channel) | Q(channel='both'))
        
        return queryset.order_by('-usage_count', 'title')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WhatsAppAccountViewSet(viewsets.ModelViewSet):
    """API endpoint for WhatsApp accounts"""
    queryset = WhatsAppAccount.objects.all()
    serializer_class = WhatsAppAccountSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a WhatsApp message"""
        account = self.get_object()
        handler = WhatsAppHandler(account)
        
        to_number = request.data.get('to_number')
        message_text = request.data.get('message')
        conversation_id = request.data.get('conversation_id')
        
        conversation = None
        if conversation_id:
            conversation = Conversation.objects.get(id=conversation_id)
        
        success, result = handler.send_text_message(to_number, message_text, conversation)
        
        if success:
            return Response({'status': 'sent', 'message_id': result})
        else:
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


class EmailAccountViewSet(viewsets.ModelViewSet):
    """API endpoint for email accounts"""
    queryset = EmailAccount.objects.all()
    serializer_class = EmailAccountSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """Trigger immediate email sync"""
        account = self.get_object()
        
        from ..tasks import sync_email_account
        sync_email_account.delay(account.id)
        
        return Response({'status': 'sync_queued'})
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        """Send an email"""
        print("FILES:", request.FILES)
        print("FILES attachments:", request.FILES.getlist('attachments'))
        
        account = self.get_object()
        handler = EmailHandler(account)
        
        to_addresses = request.data.get('to_addresses', [])
        if isinstance(to_addresses, str):
            to_addresses = [addr.strip() for addr in to_addresses.split(',') if addr.strip()]
        
        subject = request.data.get('subject')
        body = request.data.get('body')
        html_body = request.data.get('html_body')
        conversation_id = request.data.get('conversation_id')
        attachments = request.FILES.getlist('attachments')
        print("ATTACHMENTS:", attachments)
        print("Adjuntos:", attachments)
        conversation = None
        if conversation_id:
            conversation = Conversation.objects.get(id=conversation_id)
        
        success, message = handler.send_email(
            to_addresses=to_addresses,
            subject=subject,
            body=body,
            html_body=html_body,
            conversation=conversation,
            attachments=attachments 
        )
        
        if success:
            return Response({'status': 'sent'})
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)


class EmailTemplateViewSet(viewsets.ModelViewSet):
    """API endpoint for email templates"""
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(
            Q(is_global=True) | Q(created_by=self.request.user)
        )
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class EmailSignatureViewSet(viewsets.ModelViewSet):
    """API endpoint for email signatures"""
    queryset = EmailSignature.objects.all()
    serializer_class = EmailSignatureSerializer
    permission_classes = [IsAuthenticated, IsAgentOrSupervisor]
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
