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
        message_text = (request.data.get('message') or '').strip()
        conversation_id = request.data.get('conversation_id')
        attachments = request.FILES.getlist('attachments')
        
        conversation = None
        if conversation_id:
            conversation = Conversation.objects.get(id=conversation_id)

        if not attachments:
            if not message_text:
                return Response({'error': 'Por favor escribe un mensaje o adjunta archivos antes de enviar.'}, status=status.HTTP_400_BAD_REQUEST)

            success, result = handler.send_text_message(to_number, message_text, conversation)
            if success:
                return Response({'status': 'sent', 'message_id': result})
            return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)

        message_ids = []
        for idx, f in enumerate(attachments):
            media_type = handler.detect_media_type(f)

            success, media_id_or_error = handler.upload_media(f)
            if not success:
                return Response({'error': media_id_or_error}, status=status.HTTP_400_BAD_REQUEST)

            caption = message_text if (idx == 0 and message_text) else None
            filename = getattr(f, 'name', None) if media_type == 'document' else None

            success, msg_id_or_error = handler.send_media_message(
                to_number=to_number,
                media_type=media_type,
                media_id=media_id_or_error,
                caption=caption,
                filename=filename,
                conversation=conversation
            )
            if not success:
                return Response({'error': msg_id_or_error}, status=status.HTTP_400_BAD_REQUEST)
            message_ids.append(msg_id_or_error)

        return Response({'status': 'sent', 'message_ids': message_ids})


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
        """Send an email asynchronously"""
        account = self.get_object()
        
        to_addresses = request.data.get('to_addresses', [])
        if isinstance(to_addresses, str):
            to_addresses = [addr.strip() for addr in to_addresses.split(',') if addr.strip()]
        
        if not to_addresses:
            return Response({'error': 'Recipient addresses are required'}, status=status.HTTP_400_BAD_REQUEST)

        subject = request.data.get('subject') or '(Sin asunto)'
        body = request.data.get('body', '')
        html_body = request.data.get('html_body', '')
        conversation_id = request.data.get('conversation_id')
        attachments = request.FILES.getlist('attachments')
        
        conversation = None
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                pass
        
        from django.db import transaction
        from ..models import EmailQueue, EmailMessage, Message, EmailAttachment
        from django.core.files.base import ContentFile
        from ..tasks import send_queued_email

        try:
            with transaction.atomic():
                # 1. Create base Message
                content = body or html_body
                if not content and attachments:
                    content = f"📎 {len(attachments)} archivo(s) adjunto(s)"
                if not content:
                    content = '(Empty message)'

                msg = Message.objects.create(
                    conversation=conversation,
                    message_type='email',
                    direction='outbound',
                    content=content,
                    sender_name=account.name,
                    metadata={'status': 'queued'}
                )

                # 2. Create EmailMessage (as draft)
                email_msg = EmailMessage.objects.create(
                    message=msg,
                    email_account=account,
                    subject=subject,
                    html_body=html_body,
                    plain_body=body,
                    email_message_id=f"pending-{msg.id}", # Will be updated by handler
                    to_addresses=to_addresses,
                    cc_addresses=request.data.get('cc_addresses', []),
                    from_address=account.email_address
                )

                # 3. Save attachments
                for attachment in attachments:
                    file_data = attachment.read()
                    attachment.seek(0)
                    att = EmailAttachment.objects.create(
                        email_message=email_msg,
                        filename=attachment.name,
                        mime_type=getattr(attachment, 'content_type', 'application/octet-stream'),
                        size=attachment.size,
                    )
                    att.file.save(attachment.name, ContentFile(file_data), save=True)

                # 4. Create Queue entry
                queue_entry = EmailQueue.objects.create(
                    email_account=account,
                    to_addresses=to_addresses,
                    subject=subject,
                    html_body=html_body,
                    plain_body=body,
                    conversation=conversation,
                    email_message=email_msg,
                    status='pending'
                )

            # 5. Trigger task
            send_queued_email.apply_async(args=[queue_entry.id])
            
            return Response({'status': 'queued', 'queue_id': queue_entry.id}, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
